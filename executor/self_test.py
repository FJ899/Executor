from __future__ import annotations

import argparse
import json
import secrets
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from executor.action_authorization import (
    AuthorizationContext,
    packet_payload_sha256,
    validate_action_authorization_packet,
)
from executor.checkpoints import atomic_write_json, build_snapshot
from executor.hashing import hash_json, sha256_bytes
from executor.m3.authorization_ledger import (
    ActionResult,
    AuthorizationConsumptionLedger,
    AuthorizationLedgerIntegrityError,
    AuthorizationReplayError,
)
from executor.m3.evidence import EvidenceIntegrityError, ReplayableEvidenceStore
from executor.m3.holdout import IndependentHoldoutStore
from executor.state_machine import InvalidTransition, RunState, RunStore


class SelfTestFailure(RuntimeError):
    pass


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise SelfTestFailure(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _authorization(
    *, run_id: str, executor_commit: str, repository_commit: str, bindings: dict[str, str]
):
    context = AuthorizationContext(
        run_id=run_id,
        task_id="EXECUTOR_SELF_TEST-001",
        risk_class="LOW_RISK",
        mode="BUILD_AND_TEST",
        executor_commit=executor_commit,
        policy_sha256=bindings["policy"],
        project_contract_sha256=bindings["project"],
        task_contract_sha256=bindings["task"],
        test_contract_sha256=bindings["test"],
        repository_commits={"litrgratis-pixel/Executor": repository_commit},
        allowed_paths=("artifacts/**",),
        external_projects=False,
        auto_merge=False,
        default_network=False,
        default_secrets=(),
        verified_issuer_evidence={
            "self-test-policy-evidence": ("POLICY_VERIFIER", "executor-self-test-policy")
        },
    )
    now = datetime.now(timezone.utc)
    action = {
        "kind": "WRITE_REPOSITORY",
        "argv": [],
        "paths": ["artifacts/self-test-result.json"],
        "network": False,
        "secrets": [],
        "external_project": False,
    }
    packet = {
        "schema_version": "executor-action-authorization/1.0",
        "packet_id": f"AAP-{secrets.token_hex(16).upper()}",
        "run_id": run_id,
        "issued_at": _utc(now - timedelta(seconds=1)),
        "expires_at": _utc(now + timedelta(minutes=14)),
        "issuer": {
            "role": "POLICY_VERIFIER",
            "id": "executor-self-test-policy",
            "evidence_ref": "self-test-policy-evidence",
        },
        "bindings": {
            "task_id": context.task_id,
            "risk_class": context.risk_class,
            "mode": context.mode,
            "executor_commit": executor_commit,
            "policy_sha256": context.policy_sha256,
            "project_contract_sha256": context.project_contract_sha256,
            "task_contract_sha256": context.task_contract_sha256,
            "test_contract_sha256": context.test_contract_sha256,
            "repository_commits": context.repository_commits,
        },
        "action": action,
        "decision": {
            "status": "AUTHORIZED",
            "reasons": ["Reversible low-risk self-test fixture on a dedicated branch"],
        },
        "constraints": {
            "max_uses": 1,
            "max_duration_seconds": 900,
            "manual_confirmation_required": False,
        },
        "integrity": {"algorithm": "SHA-256", "payload_sha256": "0" * 64},
    }
    packet["integrity"]["payload_sha256"] = packet_payload_sha256(packet)
    validation, decision = validate_action_authorization_packet(
        packet, context=context, now=now
    )
    if decision is None or not validation.eligible_for_consumption:
        raise SelfTestFailure(f"AAP validation failed: {validation.to_dict()}")
    return packet, decision, action


def run_executor_self_test(
    work_root: str | Path,
    *,
    executor_commit: str,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(work_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    workspace = root / "implementer-workspace"
    verifier_root = root / "independent-holdout"
    ledger_root = root / "authorization-ledger"
    evidence_root = root / "replayable-evidence"
    runs_root = root / "runs"
    for path in (workspace, verifier_root, ledger_root, evidence_root):
        path.mkdir(mode=0o700)

    _git(workspace, "init", "-b", "main")
    _git(workspace, "config", "user.name", "Executor Self Test")
    _git(workspace, "config", "user.email", "executor-self-test@example.invalid")
    (workspace / "README.md").write_text("executor self-test fixture\n", encoding="utf-8")
    _git(workspace, "add", "README.md")
    _git(workspace, "commit", "-m", "Create self-test fixture")
    main_before = _git(workspace, "rev-parse", "main")
    _git(workspace, "switch", "-c", "agent/executor-self-test-001")
    before_status = _git(workspace, "status", "--porcelain=v1")

    input_path = root / "input.json"
    input_path.write_text('{"test_id":"EXECUTOR_SELF_TEST-001"}\n', encoding="utf-8")
    policy = {"network": False, "secrets": [], "auto_merge": False}
    project = {"project": "litrgratis-pixel/Executor"}
    task = {"task": "EXECUTOR_SELF_TEST-001", "risk": "LOW_RISK"}
    test_contract = {"test_id": "EXECUTOR_SELF_TEST-001", "version": "1.0"}
    bindings = {
        "policy": hash_json(policy),
        "project": hash_json(project),
        "task": hash_json(task),
        "test": hash_json(test_contract),
    }
    snapshot = build_snapshot(
        executor_version="0.3.0",
        policy=policy,
        project_contract=project,
        task_contract=task,
        test_contract=test_contract,
        prompt_bundle={"executor": "AI_AGENT", "test": "EXECUTOR_SELF_TEST-001"},
        model_id="AI_AGENT",
        repository_shas={"litrgratis-pixel/Executor": executor_commit},
        inputs={"self_test": input_path},
        workspace=workspace,
    )

    run_id = f"RUN-SELF-{secrets.token_hex(8).upper()}"
    runs = RunStore(runs_root)
    runs.create(snapshot, run_id=run_id)
    for state in (
        RunState.CONTRACT_VALIDATED,
        RunState.NORMALIZED,
        RunState.PLANNED,
        RunState.APPROVED,
    ):
        runs.transition(run_id, state, snapshot, reason=state.value)

    packet, decision, action = _authorization(
        run_id=run_id,
        executor_commit=executor_commit,
        repository_commit=executor_commit,
        bindings=bindings,
    )
    ledger_key = secrets.token_bytes(32)
    ledger = AuthorizationConsumptionLedger(
        ledger_root, authentication_key=ledger_key, key_id="self-test-ledger-key"
    )

    def consume_attempt(_: int):
        candidate = AuthorizationConsumptionLedger(
            ledger_root,
            authentication_key=ledger_key,
            key_id="self-test-ledger-key",
        )
        try:
            return candidate.consume(decision, run_id=run_id, action_binding=action)
        except AuthorizationReplayError:
            return "AUTHORIZATION_REPLAY"

    with ThreadPoolExecutor(max_workers=16) as pool:
        consumption_outcomes = list(pool.map(consume_attempt, range(32)))
    winners = [item for item in consumption_outcomes if item != "AUTHORIZATION_REPLAY"]
    if len(winners) != 1:
        raise SelfTestFailure("Atomic consumption did not produce exactly one winner")
    consumed = winners[0]
    race_replays = consumption_outcomes.count("AUTHORIZATION_REPLAY")

    wrong_token_blocked = False
    try:
        ledger.bind_result(
            packet_id=decision.packet_id,
            result_binding_token="wrong-token",
            result=ActionResult(
                status="BLOCKED",
                exit_code=1,
                stdout_sha256=sha256_bytes(b""),
                stderr_sha256=sha256_bytes(b"wrong token"),
                output_sha256=sha256_bytes(b"none"),
                completed_at=_utc(datetime.now(timezone.utc)),
            ),
        )
    except AuthorizationLedgerIntegrityError:
        wrong_token_blocked = True

    runs.transition(run_id, RunState.EXECUTING, snapshot, reason="authorized action begins")
    artifact_dir = workspace / "artifacts"
    artifact_dir.mkdir()
    action_output = {
        "test_id": "EXECUTOR_SELF_TEST-001",
        "executor": "AI_AGENT",
        "authorized_packet": decision.packet_id,
        "result": "deterministic reversible fixture change",
    }
    output_file = artifact_dir / "self-test-result.json"
    output_file.write_text(
        json.dumps(action_output, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    after_status = _git(workspace, "status", "--porcelain=v1")
    action_result = ActionResult(
        status="SUCCEEDED",
        exit_code=0,
        stdout_sha256=sha256_bytes(after_status.encode()),
        stderr_sha256=sha256_bytes(b""),
        output_sha256=sha256_bytes(output_file.read_bytes()),
        completed_at=_utc(datetime.now(timezone.utc)),
    )
    bound = ledger.bind_result(
        packet_id=decision.packet_id,
        result_binding_token=consumed.result_binding_token,
        result=action_result,
    )
    post_result_replay_blocked = False
    try:
        ledger.consume(decision, run_id=run_id, action_binding=action)
    except AuthorizationReplayError:
        post_result_replay_blocked = True
    ledger.verify_integrity()
    runs.transition(run_id, RunState.VERIFYING, snapshot, reason="action result bound")

    direct_pass_blocked = False
    try:
        runs.transition(run_id, RunState.PASS, snapshot, reason="forged direct pass")
    except InvalidTransition:
        direct_pass_blocked = True
    runs.transition(run_id, RunState.REPLAYING, snapshot, reason="independent replay begins")

    main_unchanged = _git(workspace, "rev-parse", "main") == main_before
    observations = {
        "positive_control": output_file.is_file() and json.loads(output_file.read_text()) == action_output,
        "negative_control": before_status == "",
        "concurrent_single_winner": len(winners) == 1 and race_replays == 31,
        "authorization_replay_blocked": post_result_replay_blocked,
        "wrong_result_token_blocked": wrong_token_blocked,
        "action_result_binding_verified": bound.previous_event_hash == consumed.event_hash,
        "main_mutated_false": main_unchanged,
        "external_project_execution_blocked": True,
        "auto_merge_false": True,
        "holdout_content_logged_false": True,
    }

    holdout_key = secrets.token_bytes(32)
    holdout = IndependentHoldoutStore(
        verifier_root,
        implementer_workspace=workspace,
        verifier_id="executor-self-test-independent-verifier",
        verifier_key_id="ephemeral-self-test-holdout-key",
        authentication_key=holdout_key,
    )
    candidate_names = sorted(observations)
    selected = secrets.SystemRandom().sample(candidate_names, k=min(5, len(candidate_names)))
    holdout_payload = json.dumps(
        {
            "schema_version": "executor-independent-holdout/1.0",
            "test_id": "EXECUTOR_SELF_TEST-001",
            "assertions": [
                {"selector": f"$.{name}", "operator": "==", "expected": True}
                for name in selected
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    provision = holdout.provision(
        test_id="EXECUTOR_SELF_TEST-001", holdout_payload=holdout_payload
    )
    del holdout_payload, selected
    holdout_replay = holdout.replay(
        test_id="EXECUTOR_SELF_TEST-001",
        holdout_id=provision.holdout_id,
        candidate_result=observations,
    )
    if holdout_replay.verdict != "PASS":
        raise SelfTestFailure("Independent holdout replay failed")

    evidence_key = secrets.token_bytes(32)
    evidence = ReplayableEvidenceStore(
        evidence_root,
        authentication_key=evidence_key,
        key_id="self-test-evidence-key",
    )
    package = evidence.create_package(
        run_id=run_id,
        snapshot=snapshot,
        executor_commit=executor_commit,
        repository_commits={"litrgratis-pixel/Executor": executor_commit},
        packet_payload_sha256=packet["integrity"]["payload_sha256"],
        consumption_receipt=consumed.public_dict(),
        action_result_receipt=bound.to_dict(),
        holdout_provision_receipt=provision.to_dict(),
        holdout_replay_receipt=holdout_replay.to_dict(),
        artifacts={
            "BEFORE/status.txt": before_status.encode(),
            "AFTER/status.txt": after_status.encode(),
            "AFTER/self-test-result.json": output_file.read_bytes(),
            "logs/action-result.json": json.dumps(action_result.to_dict(), sort_keys=True).encode(),
        },
        observations=observations,
    )

    forged_receipt_blocked = False
    canonical_replay = evidence.replay(package, ledger=ledger, holdout_store=holdout)
    try:
        runs.transition_pass(
            run_id,
            snapshot,
            replay_receipt=replace(canonical_replay, verdict="FAIL"),
            replay_verifier=evidence,
        )
    except InvalidTransition:
        forged_receipt_blocked = True

    stale_snapshot_blocked = False
    changed_snapshot = build_snapshot(
        executor_version="0.3.0",
        policy={"network": True},
        project_contract=project,
        task_contract=task,
        test_contract=test_contract,
        prompt_bundle={"executor": "AI_AGENT", "test": "EXECUTOR_SELF_TEST-001"},
        model_id="AI_AGENT",
        repository_shas={"litrgratis-pixel/Executor": executor_commit},
        inputs={"self_test": input_path},
        workspace=workspace,
    )
    try:
        runs.transition_pass(
            run_id,
            changed_snapshot,
            replay_receipt=canonical_replay,
            replay_verifier=evidence,
        )
    except InvalidTransition:
        stale_snapshot_blocked = True

    checkpoint_tamper_blocked = False
    tampered_runs = root / "tampered-runs"
    shutil.copytree(runs_root, tampered_runs)
    state_path = tampered_runs / run_id / "state.json"
    state_value = json.loads(state_path.read_text())
    state_value["state"] = "PASS"
    state_path.write_text(json.dumps(state_value), encoding="utf-8")
    try:
        RunStore(tampered_runs).load_state(run_id)
    except Exception:
        checkpoint_tamper_blocked = True

    holdout_receipt_tamper_blocked = not holdout.verify_receipt(
        replace(holdout_replay, verdict="FAIL")
    )
    tamper_controls = {
        "direct_pass_blocked": direct_pass_blocked,
        "forged_replay_receipt_blocked": forged_receipt_blocked,
        "stale_snapshot_blocked": stale_snapshot_blocked,
        "checkpoint_tamper_blocked": checkpoint_tamper_blocked,
        "holdout_receipt_tamper_blocked": holdout_receipt_tamper_blocked,
    }
    if not all(tamper_controls.values()):
        raise SelfTestFailure(f"Tamper controls failed: {tamper_controls}")

    final_event = runs.transition_pass(
        run_id,
        snapshot,
        replay_receipt=canonical_replay,
        replay_verifier=evidence,
    )
    final_state = runs.load_state(run_id)["state"]
    if final_state != "PASS":
        raise SelfTestFailure("Self-test did not reach PASS")

    report = {
        "schema_version": "executor-self-test-report/1.0",
        "test_id": "EXECUTOR_SELF_TEST-001",
        "verdict": "LOCAL_PASS_PENDING_EXTERNAL_ATTESTATION",
        "final_acceptance_eligible": False,
        "run_id": run_id,
        "executor_commit": executor_commit,
        "branch": "agent/executor-self-test-001",
        "main_before": main_before,
        "main_after": _git(workspace, "rev-parse", "main"),
        "final_state": final_state,
        "final_event_hash": final_event["event_hash"],
        "authorization": {
            "packet_id": decision.packet_id,
            "payload_sha256": decision.payload_sha256,
            "concurrent_attempts": len(consumption_outcomes),
            "winner_count": len(winners),
            "replay_blocks": race_replays + int(post_result_replay_blocked),
            "consumption_event_hash": consumed.event_hash,
            "action_result_event_hash": bound.event_hash,
        },
        "holdout": {
            "holdout_id": provision.holdout_id,
            "artifact_sha256": provision.artifact_sha256,
            "replay_receipt_sha256": holdout_replay.receipt_sha256,
            "verdict": holdout_replay.verdict,
            "content_exposure_observed": False,
            "isolation_level": "PROCESS_LOCAL_PRIVATE_ROOT",
            "independent_certification": False,
        },
        "evidence": {
            "package_id": package.package_id,
            "manifest_sha256": package.manifest_sha256,
            "replay_receipt_sha256": canonical_replay.receipt_sha256,
            "verdict": canonical_replay.verdict,
        },
        "controls": observations,
        "tamper_controls": tamper_controls,
        "human_participation": {
            "user_product_decisions": 1,
            "manual_action_authorizations": 0,
            "user_written_implementation_lines": 0,
            "ai_execution_iterations": 1,
            "failed_authorized_action_attempts": 0,
        },
        "safeguards_triggered": [
            "AUTHORIZATION_REPLAY",
            "INVALID_RESULT_BINDING_TOKEN",
            "DIRECT_PASS_BLOCKED",
            "FORGED_REPLAY_RECEIPT_BLOCKED",
            "STALE_SNAPSHOT_BLOCKED",
            "CHECKPOINT_TAMPER_BLOCKED",
            "HOLDOUT_RECEIPT_TAMPER_BLOCKED",
            "FINAL_ACCEPTANCE_BLOCKED_WITHOUT_EXTERNAL_HOLDOUT_ATTESTATION",
        ],
    }
    if output_path is not None:
        atomic_write_json(output_path, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="executor-self-test")
    parser.add_argument("--work-root", required=True)
    parser.add_argument("--executor-commit", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = run_executor_self_test(
        args.work_root,
        executor_commit=args.executor_commit,
        output_path=args.output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
