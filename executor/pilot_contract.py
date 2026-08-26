from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone
from typing import Any

from executor.frozen_pilot_authority import (
    REVOCATION_CUTOFF,
    RecordingGitHubSource,
    authority_snapshot_sha256,
    build_authority_snapshot,
)
from executor.github_authority import GovernedAuthorityLedger
from executor.github_trust import (
    GitHubEvidenceSource,
    GitHubTrustError,
    GitHubTrustProfile,
    VerifiedGitHubDecision,
    VerifiedGitHubRequest,
    canonical_json,
    verify_github_decision,
    verify_github_request,
)
from executor.gp001_contract import validate_gp001_task_contract


class PilotContractError(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _draft_hash_material(draft: dict[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(draft)
    request_evidence = material.get("request_evidence")
    if not isinstance(request_evidence, dict):
        raise PilotContractError("draft request evidence is missing")
    request_evidence.pop("observed_at", None)
    return material


def pilot_draft_sha256(draft: dict[str, Any]) -> str:
    material = _draft_hash_material(draft)
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def _require_sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PilotContractError(f"{label} must be a lowercase SHA-256")
    return value


def _require_git_sha(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PilotContractError(f"{label} must be a lowercase 40-character Git SHA")
    return value


def _require_nonempty_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PilotContractError(f"{label} must be a non-empty string")
    return value


def build_pilot_draft(request: VerifiedGitHubRequest) -> dict[str, Any]:
    target = copy.deepcopy(request.payload["target"])
    task = copy.deepcopy(request.payload["task"])
    return {
        "schema_version": "executor-pilot-draft/1.0",
        "request_id": request.payload["request_id"],
        "request_evidence": request.to_dict(),
        "target": target,
        "task": task,
        "authority_boundary": {
            "provider": "GITHUB",
            "required_decisions": ["ACCEPT", "MODIFY", "REJECT"],
            "effect": "BOUNDED_DRAFT_PR_ONLY",
            "merge": False,
            "deploy": False,
            "release": False,
            "global_consumption": "GITHUB_REF_REQUIRED",
        },
        "solution_boundary": {
            "owner": "EXTERNAL_INTELLIGENCE",
            "effect_authority": False,
        },
        "status": "AWAITING_VERIFIED_GITHUB_DECISION",
        "executable": False,
    }


def _validate_formation_draft_schema(draft: dict[str, Any]) -> None:
    expected_keys = {
        "schema_version",
        "executor_repository",
        "executor_commit",
        "profile_id",
        "profile_sha256",
        "canonical_task_sha256",
        "request_id",
        "draft_version",
        "supersedes_draft_sha256",
        "user_request",
        "understood_objective",
        "provenance",
        "proposed_task_contract",
        "out_of_scope_discoveries",
        "open_questions",
    }
    if set(draft) != expected_keys:
        raise PilotContractError("formation draft schema fields are incomplete or unexpected")
    if draft.get("schema_version") != "executor-contract-formation-draft/1.0":
        raise PilotContractError("formation draft schema is missing or unsupported")
    if draft.get("executor_repository") != "FJ899/Executor":
        raise PilotContractError("formation draft executor repository is unsupported")
    if draft.get("profile_id") != "REQUEST_TO_CONTRACT_001":
        raise PilotContractError("formation draft profile is unsupported")

    _require_git_sha(draft.get("executor_commit"), label="formation executor_commit")
    _require_sha256(draft.get("profile_sha256"), label="formation profile_sha256")
    _require_sha256(
        draft.get("canonical_task_sha256"),
        label="formation canonical_task_sha256",
    )
    _require_nonempty_string(draft.get("request_id"), label="formation request_id")
    user_request = _require_nonempty_string(
        draft.get("user_request"), label="formation user_request"
    )
    understood_objective = _require_nonempty_string(
        draft.get("understood_objective"), label="formation understood_objective"
    )

    draft_version = draft.get("draft_version")
    if type(draft_version) is not int or draft_version < 1:
        raise PilotContractError("formation draft_version must be a positive integer")
    supersedes = draft.get("supersedes_draft_sha256")
    if draft_version == 1:
        if supersedes is not None:
            raise PilotContractError("formation draft version 1 cannot supersede another draft")
    else:
        _require_sha256(supersedes, label="formation supersedes_draft_sha256")

    discoveries = draft.get("out_of_scope_discoveries")
    if not isinstance(discoveries, list) or not all(
        isinstance(item, str) and item.strip() for item in discoveries
    ):
        raise PilotContractError("formation out-of-scope discoveries are malformed")
    open_questions = draft.get("open_questions")
    if open_questions != []:
        raise PilotContractError("formation draft with unresolved questions cannot freeze")

    provenance = draft.get("provenance")
    if not isinstance(provenance, list) or not provenance:
        raise PilotContractError("formation provenance is missing")
    user_records = []
    objective_records = []
    for record in provenance:
        if not isinstance(record, dict):
            raise PilotContractError("formation provenance record must be an object")
        allowed_keys = {"path", "source", "value", "note", "confidence"}
        required_keys = {"path", "source", "value", "note"}
        if not required_keys.issubset(record) or not set(record).issubset(allowed_keys):
            raise PilotContractError("formation provenance record schema is invalid")
        path = _require_nonempty_string(record.get("path"), label="formation provenance path")
        source = record.get("source")
        if source not in {"USER", "MODEL"}:
            raise PilotContractError("formation provenance source must be USER or MODEL")
        if not isinstance(record.get("note"), str):
            raise PilotContractError("formation provenance note must be a string")
        if "confidence" in record:
            confidence = record.get("confidence")
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not 0.0 <= float(confidence) <= 1.0
            ):
                raise PilotContractError("formation provenance confidence is invalid")
        if source == "USER":
            user_records.append(record)
        if (
            source == "MODEL"
            and path == "$.understood_objective"
            and record.get("value") == understood_objective
        ):
            objective_records.append(record)

    if len(user_records) != 1:
        raise PilotContractError("formation draft must contain exactly one direct USER provenance record")
    if (
        user_records[0].get("path") != "$.user_request"
        or user_records[0].get("value") != user_request
    ):
        raise PilotContractError("formation USER provenance does not bind the verbatim request")
    if not objective_records:
        raise PilotContractError("formation MODEL provenance does not bind the understood objective")

    proposed_task = draft.get("proposed_task_contract")
    if not isinstance(proposed_task, dict):
        raise PilotContractError("formation proposed task contract is missing")
    if proposed_task.get("id") != "GP001-FIX-FAILING-TEST-CASE-001":
        raise PilotContractError("formation proposed task is not the bounded GP001 task")
    validation = validate_gp001_task_contract(proposed_task)
    if validation.issues:
        first = validation.issues[0]
        raise PilotContractError(
            f"formation proposed task is invalid: {first.path}: {first.message}"
        )


def _validate_request_projection_from_formation_draft(
    draft: dict[str, Any],
    *,
    authority_draft_sha256: str,
    request_payload: dict[str, Any],
) -> None:
    _validate_formation_draft_schema(draft)

    computed_hash = hashlib.sha256(canonical_json(draft).encode("utf-8")).hexdigest()
    if computed_hash != authority_draft_sha256:
        raise PilotContractError("formation binding draft content hash mismatch")

    proposed_task = draft["proposed_task_contract"]
    repositories = proposed_task["repositories"]
    target = repositories["target"]
    golden = proposed_task["golden_path"]
    problem = golden["problem"]
    scope = golden["scope"]
    commands = golden["commands"]
    budgets = proposed_task["budgets"]

    allowed_paths = copy.deepcopy(scope["allowed_paths"])
    if not 1 <= len(allowed_paths) <= 3:
        raise PilotContractError("formation authority projection exceeds the bounded file limit")
    target_test = copy.deepcopy(commands["target_test_argv"])
    expected_task = {
        "class": "BOUNDED_CORRECTNESS_OR_QUALITY_FIX",
        "problem_statement": problem["statement"],
        "allowed_paths": allowed_paths,
        "protected_paths": copy.deepcopy(scope["protected_paths"]),
        "precondition_argv": [target_test],
        "postcondition_argv": [copy.deepcopy(target_test)],
        "regression_argv": copy.deepcopy(commands["regression_argv"]),
        "max_production_files": len(allowed_paths),
        "max_patch_lines": budgets["max_patch_lines"],
    }
    expected_target = {
        "repository": target["name"],
        "commit": target["commit"],
    }
    actual_target = request_payload.get("target")
    if not isinstance(actual_target, dict):
        raise PilotContractError("GitHub authority request target is missing")
    actual_stable_target = {
        "repository": actual_target.get("repository"),
        "commit": actual_target.get("commit"),
    }
    expected_nonce = (
        f"formation-{draft['draft_version']}-{authority_draft_sha256[:24]}"
    )
    if (
        request_payload.get("schema_version") != "executor-github-request/1.0"
        or request_payload.get("request_id") != draft["request_id"]
        or actual_stable_target != expected_target
        or request_payload.get("task") != expected_task
        or request_payload.get("nonce") != expected_nonce
    ):
        raise PilotContractError(
            "GitHub authority request does not match governed formation draft projection"
        )


def _validate_formation_binding(
    binding: dict[str, Any],
    *,
    authority_draft_sha256: str,
    request_payload: dict[str, Any],
    request_id: str,
) -> None:
    if binding.get("schema_version") != "executor-contract-formation-binding/1.0":
        raise PilotContractError("formation binding schema is missing or unsupported")

    draft = binding.get("draft")
    if not isinstance(draft, dict):
        raise PilotContractError("formation binding draft is missing")
    _validate_request_projection_from_formation_draft(
        draft,
        authority_draft_sha256=authority_draft_sha256,
        request_payload=request_payload,
    )
    if binding.get("draft_sha256") != authority_draft_sha256:
        raise PilotContractError("formation binding draft hash mismatch")

    if binding.get("request_id") != request_id or draft.get("request_id") != request_id:
        raise PilotContractError("formation binding request id mismatch")
    if binding.get("authority_request_payload") != request_payload:
        raise PilotContractError("formation binding request payload mismatch")
    expected_request_sha256 = hashlib.sha256(
        canonical_json(request_payload).encode("utf-8")
    ).hexdigest()
    if binding.get("authority_request_payload_sha256") != expected_request_sha256:
        raise PilotContractError("formation binding request payload hash mismatch")

    expected_pairs = (
        ("executor_repository", "executor_repository"),
        ("executor_commit", "executor_commit"),
        ("formation_profile_sha256", "profile_sha256"),
        ("canonical_task_sha256", "canonical_task_sha256"),
        ("draft_version", "draft_version"),
        ("supersedes_draft_sha256", "supersedes_draft_sha256"),
    )
    for binding_key, draft_key in expected_pairs:
        if binding.get(binding_key) != draft.get(draft_key):
            raise PilotContractError(
                f"formation binding {binding_key} differs from hashed formation draft"
            )
    if binding.get("formation_profile") != draft.get("profile_id"):
        raise PilotContractError(
            "formation binding profile identity differs from hashed formation draft"
        )

    invalidated = binding.get("invalidated_draft_sha256s")
    if not isinstance(invalidated, list) or not all(
        isinstance(item, str) and len(item) == 64 for item in invalidated
    ):
        raise PilotContractError("formation invalidated draft set is malformed")
    supersedes = binding.get("supersedes_draft_sha256")
    if supersedes is not None and supersedes not in invalidated:
        raise PilotContractError(
            "formation superseded draft is not recorded as invalidated"
        )


def apply_github_decision(
    *,
    draft: dict[str, Any],
    decision: VerifiedGitHubDecision,
    source: GitHubEvidenceSource,
    profile: GitHubTrustProfile,
    ledger: GovernedAuthorityLedger,
    authority_draft_sha256: str | None = None,
    expected_request_payload: dict[str, Any] | None = None,
    formation_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Final-live verify and consume one exact GitHub contract decision.

    Existing P4 callers keep the canonical pilot draft as the authority-bearing
    identity. Contract formation may use a different governed draft hash only
    when the exact generated provider request and complete formation binding are
    supplied together and independently validated before authority consumption.
    """

    formation_values = (
        authority_draft_sha256,
        expected_request_payload,
        formation_binding,
    )
    formation_mode = any(value is not None for value in formation_values)
    if formation_mode and not all(value is not None for value in formation_values):
        raise PilotContractError(
            "formation authority override requires draft hash, request payload and binding"
        )

    current = _utc_now().astimezone(timezone.utc)
    recording = RecordingGitHubSource(source)
    final_request = verify_github_request(
        recording,
        profile=profile,
        issue_number=decision.issue_number,
        now=current,
    )

    final_draft = build_pilot_draft(final_request)
    pilot_draft_hash = pilot_draft_sha256(final_draft)
    if pilot_draft_hash != pilot_draft_sha256(draft):
        raise PilotContractError("GitHub request changed before final live verification")

    if formation_mode:
        if not isinstance(expected_request_payload, dict):
            raise PilotContractError("formation expected request payload must be an object")
        if final_request.payload != expected_request_payload:
            raise PilotContractError(
                "GitHub request payload differs from the governed formation export"
            )
        authority_hash = _require_sha256(
            authority_draft_sha256,
            label="authority_draft_sha256",
        )
        if not isinstance(formation_binding, dict):
            raise PilotContractError("formation binding must be an object")
        _validate_formation_binding(
            formation_binding,
            authority_draft_sha256=authority_hash,
            request_payload=final_request.payload,
            request_id=str(final_draft.get("request_id", "")),
        )
    else:
        authority_hash = pilot_draft_hash

    if decision.draft_sha256 != authority_hash:
        raise PilotContractError(
            "reviewed GitHub decision is bound to a different authority draft"
        )

    final_decision = verify_github_decision(
        recording,
        profile=profile,
        request=final_request,
        comment_id=decision.comment_id,
        draft_sha256=authority_hash,
        now=current,
    )
    if (
        final_decision.comment_id != decision.comment_id
        or final_decision.comment_node_id != decision.comment_node_id
    ):
        raise PilotContractError(
            "final GitHub decision identity differs from reviewed decision"
        )

    snapshot = build_authority_snapshot(
        recording=recording,
        request=final_request,
        decision=final_decision,
        draft_sha256=authority_hash,
    )
    snapshot_sha256 = authority_snapshot_sha256(snapshot)
    consumption = ledger.consume(
        authority_key=f"github-decision:{final_decision.comment_node_id}",
        payload_sha256=snapshot_sha256,
        action_kind=f"CONTRACT_{final_decision.decision}",
        run_id=str(final_draft.get("request_id", "")),
        not_after=final_decision.expires_at,
    )

    if final_decision.decision == "MODIFY":
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "MODIFICATION_REQUIRED",
            "draft_sha256": authority_hash,
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "decision_evidence": final_decision.to_dict(),
            "executable": False,
        }
    elif final_decision.decision == "REJECT":
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "REJECTED",
            "draft_sha256": authority_hash,
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "decision_evidence": final_decision.to_dict(),
            "executable": False,
        }
    elif final_decision.decision == "ACCEPT":
        contract = {
            "schema_version": "executor-frozen-pilot-contract/1.0",
            "request_id": final_draft["request_id"],
            "target": copy.deepcopy(final_draft["target"]),
            "task": copy.deepcopy(final_draft["task"]),
            "request_evidence": final_request.to_dict(),
            "decision_evidence": final_decision.to_dict(),
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "draft_sha256": authority_hash,
            "authority_boundary": {
                **copy.deepcopy(final_draft["authority_boundary"]),
                "revocation_cutoff": REVOCATION_CUTOFF,
            },
            "solution_boundary": copy.deepcopy(final_draft["solution_boundary"]),
            "status": "AUTHORIZED_AND_FROZEN",
            "executable": True,
        }
        if formation_mode:
            contract["formation_binding"] = copy.deepcopy(formation_binding)
        contract_sha256 = hashlib.sha256(
            canonical_json(contract).encode("utf-8")
        ).hexdigest()
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "AUTHORIZED_AND_FROZEN",
            "contract": contract,
            "contract_sha256": contract_sha256,
            "draft_sha256": authority_hash,
            "authority_snapshot_sha256": snapshot_sha256,
            "decision_evidence": final_decision.to_dict(),
            "executable": True,
        }
    else:
        raise GitHubTrustError("unsupported verified GitHub decision")

    result["decision_consumption"] = ledger.bind_result(
        consumption=consumption,
        result=result,
    )
    return result
