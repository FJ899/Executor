from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import signal
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from executor.github_trust import canonical_json
from executor.stage3_evidence import Stage3EvidenceError, sha256_bytes, sha256_json, validate_external_negative_observation
from executor.stage3_generation_trust import (
    Stage3GenerationTrustError,
    Stage3GenerationTrustProfile,
    _expected_request,
    _validate_evidence_semantics,
    _verify_attestation_offline,
)
from executor.stage3_workspace import (
    Stage3WorkspaceError,
    _install_descriptor_only_seccomp,
    apply_exact_descriptor_replacement,
    open_validated_target_readonly,
    reopen_target_for_effect,
    verify_pinned_clean_workspace,
)
from executor.stage3_runtime import Stage3RuntimeError, _revalidate_exact_mutation_scope
from tests.test_stage3_runtime import make_loose_git_fixture


def _profile() -> Stage3GenerationTrustProfile:
    return Stage3GenerationTrustProfile(
        oidc_issuer="https://token.actions.githubusercontent.com",
        repository="FJ899/Executor",
        signer_reusable_workflow=".github/workflows/stage3-generation-verifier-attestation.yml",
        signer_digest="a" * 40,
        accepted_predicate_type="https://fj899.github.io/Executor/attestations/provider-generation-evidence/v1",
        accepted_evidence_schema="executor-provider-generation-evidence/1.0",
        verification_method="OPENAI_RESPONSES_RETRIEVE_V1",
        trusted_root_sha256="b" * 64,
        policy_sha256="c" * 64,
    )


def _provider_inputs() -> tuple[dict, dict, dict, dict]:
    frozen = {
        "contract": {
            "request_evidence": {
                "repository": "FJ899/fixture",
                "issue_number": 9,
                "issue_node_id": "I_kwDOfixture",
                "body_sha256": "1" * 64,
            }
        },
        "decision_consumption": {"state": "FINAL", "terminal_success": True, "receipt": "fixed"},
    }
    proposal = {
        "contract_sha256": "2" * 64,
        "repository": "FJ899/fixture",
        "source_commit": "3" * 40,
        "source_tree": "4" * 40,
        "provenance": {"generated_at": "2026-08-27T18:00:00Z"},
    }
    stage2 = {
        "provider": "OpenAI",
        "model": "gpt-5.6-sol",
        "generation_evidence_ref": "resp_stage3_fixture",
        "context_sha256": "5" * 64,
        "prompt_sha256": "6" * 64,
        "generation_response_sha256": "7" * 64,
        "generation_challenge_sha256": "8" * 64,
        "generation_challenge_issued_at": "2026-08-27T17:59:00Z",
        "proposal_sha256": "9" * 64,
    }
    profile = _profile()
    request = _expected_request(frozen_result=frozen, stage2_result=stage2, proposal=proposal)
    evidence = {
        "schema_version": "executor-provider-generation-evidence/1.0",
        "provider": request["provider"],
        "model": request["model"],
        "generation_evidence_ref": request["generation_evidence_ref"],
        "provider_record_id": request["generation_evidence_ref"],
        "provider_generation_timestamp": request["provider_generation_timestamp"],
        "frozen_task_contract_sha256": request["frozen_task_contract_sha256"],
        "repository": request["repository"],
        "source_commit": request["source_commit"],
        "source_tree": request["source_tree"],
        "source_context_sha256": request["source_context_sha256"],
        "prompt_sha256": request["prompt_sha256"],
        "response_sha256": request["response_sha256"],
        "generation_challenge_sha256": request["generation_challenge_sha256"],
        "generation_challenge_issued_at": request["generation_challenge_issued_at"],
        "terminal_freeze_receipt_sha256": request["terminal_freeze_receipt_sha256"],
        "proposal_payload_sha256": request["proposal_payload_sha256"],
        "verification_method": "OPENAI_RESPONSES_RETRIEVE_V1",
        "verifier_repository": profile.repository,
        "verifier_reusable_workflow_path": profile.signer_reusable_workflow,
        "verifier_workflow_source_commit": profile.signer_digest,
        "verification_request_sha256": sha256_json(request),
        "evidence_hash_construction": "SHA256_CANONICAL_JSON_WITHOUT_EVIDENCE_ARTIFACT_SHA256",
        "attestation_predicate_type": profile.accepted_predicate_type,
        "evidence_artifact_sha256": "0" * 64,
    }
    material = dict(evidence)
    material.pop("evidence_artifact_sha256")
    evidence["evidence_artifact_sha256"] = sha256_json(material)
    return frozen, stage2, proposal, evidence


def _rehash_evidence(value: dict) -> bytes:
    value = copy.deepcopy(value)
    value.pop("evidence_artifact_sha256", None)
    digest = sha256_json(value)
    value["evidence_artifact_sha256"] = digest
    return canonical_json(value).encode("utf-8")


def test_reusable_verifier_workflow_is_closed_and_pinned() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = root / ".github/workflows/stage3-generation-verifier-attestation.yml"
    raw = workflow.read_text(encoding="utf-8")
    parsed = yaml.load(raw, Loader=yaml.BaseLoader)
    assert set(parsed) >= {"name", "on", "permissions", "jobs"}
    assert set(parsed["on"]) == {"workflow_call"}
    forbidden = (
        "push", "pull_request", "pull_request_target", "workflow_dispatch",
        "repository_dispatch", "schedule", "issue_comment",
    )
    assert all(trigger not in parsed["on"] for trigger in forbidden)
    assert parsed["permissions"] == {
        "contents": "read", "id-token": "write", "attestations": "write"
    }
    jobs = parsed["jobs"]
    assert len(jobs) == 1
    job = next(iter(jobs.values()))
    assert job["runs-on"] == "ubuntu-latest"
    uses = [step["uses"] for step in job["steps"] if "uses" in step]
    assert uses == ["actions/attest@f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6"]
    assert "actions/checkout" not in raw
    assert "self-hosted runner is forbidden" in raw
    assert "api.openai.com/v1" in raw
    assert "job.workflow_repository" in raw
    assert "job.workflow_file_path" in raw
    assert "job.workflow_sha" in raw


@pytest.mark.parametrize(
    "field,bad",
    [
        ("provider_record_id", "resp_other"),
        ("response_sha256", "f" * 64),
        ("verifier_workflow_source_commit", "d" * 40),
        ("verifier_reusable_workflow_path", ".github/workflows/upload-download.yml"),
        ("attestation_predicate_type", "https://example.invalid/wrong"),
    ],
)
def test_provider_evidence_mismatch_is_rejected(field: str, bad: str) -> None:
    frozen, stage2, proposal, evidence = _provider_inputs()
    evidence[field] = bad
    raw = _rehash_evidence(evidence)
    evidence = json.loads(raw)
    with pytest.raises(Stage3GenerationTrustError):
        _validate_evidence_semantics(
            evidence,
            raw=raw,
            profile=_profile(),
            frozen_result=frozen,
            stage2_result=stage2,
            proposal=proposal,
        )


def test_caller_created_matching_evidence_has_no_runtime_trust_path() -> None:
    from executor import stage3_generation_trust as trust
    import inspect

    sig = inspect.signature(trust.verify_provider_generation_binding)
    assert "verifier" not in sig.parameters
    assert "trust_root" not in sig.parameters
    assert "identity_policy" not in sig.parameters
    source = inspect.getsource(trust.verify_provider_generation_binding)
    assert "_load_profile()" in source
    assert "_verify_attestation_offline" in source


@pytest.mark.parametrize("case", ["hardlink", "symlink", "nonexistent"])
def test_invalid_target_surfaces_are_rejected(tmp_path: Path, case: str) -> None:
    root, commit, tree, _ = make_loose_git_fixture(tmp_path)
    _, entries = verify_pinned_clean_workspace(
        root, repository="FJ899/fixture", expected_repository="FJ899/fixture", commit=commit, tree=tree
    )
    target = root / "target.txt"
    path = "target.txt"
    if case == "hardlink":
        os.link(target, root / "alias.txt")
    elif case == "symlink":
        victim = root / "victim.txt"
        victim.write_text("victim", encoding="utf-8")
        target.unlink()
        target.symlink_to(victim.name)
    else:
        target.unlink()
    with pytest.raises(Stage3WorkspaceError):
        open_validated_target_readonly(
            root,
            path=path,
            expected_before_sha256=sha256_bytes(b"before\n"),
            tree_entries=entries,
        )


def test_dirty_wrong_source_and_wrong_replacement_are_rejected(tmp_path: Path) -> None:
    root, commit, tree, _ = make_loose_git_fixture(tmp_path)
    (root / "extra.txt").write_text("dirty", encoding="utf-8")
    with pytest.raises(Stage3WorkspaceError, match="clean"):
        verify_pinned_clean_workspace(
            root, repository="FJ899/fixture", expected_repository="FJ899/fixture", commit=commit, tree=tree
        )
    (root / "extra.txt").unlink()
    with pytest.raises(Stage3WorkspaceError):
        verify_pinned_clean_workspace(
            root, repository="wrong/repo", expected_repository="FJ899/fixture", commit=commit, tree=tree
        )
    with pytest.raises(Stage3WorkspaceError):
        verify_pinned_clean_workspace(
            root, repository="FJ899/fixture", expected_repository="FJ899/fixture", commit="0" * 40, tree=tree
        )
    _, entries = verify_pinned_clean_workspace(
        root, repository="FJ899/fixture", expected_repository="FJ899/fixture", commit=commit, tree=tree
    )
    fd, snap = open_validated_target_readonly(
        root, path="target.txt", expected_before_sha256=sha256_bytes(b"before\n"), tree_entries=entries
    )
    os.close(fd)
    write_fd = os.open(root / "target.txt", os.O_RDWR)
    try:
        with pytest.raises(Stage3WorkspaceError, match="after hash"):
            apply_exact_descriptor_replacement(
                write_fd,
                replacement=b"not the declared after bytes",
                expected_after_sha256="0" * 64,
                pre_effect=snap,
            )
    finally:
        os.close(write_fd)


def _run_forbidden_syscall(kind: str) -> int:
    pid = os.fork()
    if pid == 0:
        try:
            _install_descriptor_only_seccomp()
            if kind == "open":
                os.open("/", os.O_RDONLY)
            elif kind == "socket":
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            elif kind == "execve":
                os.execve("/bin/true", ["true"], {})
            elif kind == "unlink":
                os.unlink("/definitely-not-a-real-stage3-path")
            os._exit(101)
        except BaseException:
            os._exit(102)
    _, status = os.waitpid(pid, 0)
    return status


@pytest.mark.skipif(platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}, reason="Stage-3 worker environment is Linux x86_64")
@pytest.mark.parametrize("kind", ["open", "socket", "execve", "unlink"])
def test_descriptor_worker_seccomp_kills_forbidden_syscalls(kind: str) -> None:
    status = _run_forbidden_syscall(kind)
    assert os.WIFSIGNALED(status)
    assert os.WTERMSIG(status) == signal.SIGSYS


def _observer(**updates) -> dict:
    value = {
        "schema_version": "executor-stage3-host-observer/1.0",
        "observer_id": "p4-host-observer",
        "workspace_instance_id": "workspace-stage3-001",
        "repository_write_targets": ["target.txt"],
        "writable_mount_set": ["/workspace", "/workspace/repo", "/workspace/.stage3-control"],
        "network_effect_count": 0,
        "secret_exposure_count": 0,
        "post_worker_exec_count": 0,
        "git_publication_effect_count": 0,
        "git_metadata_write_count": 0,
        "control_input_write_count": 0,
        "task_command_exec_count": 0,
        "host_write_outside_allocation_count": 0,
        "worker_stopped_receipt_sha256": "a" * 64,
        "raw_observation_sha256": "b" * 64,
    }
    value.update(updates)
    return value


@pytest.mark.parametrize(
    "updates",
    [
        {"repository_write_targets": ["target.txt", "second.txt"]},
        {"network_effect_count": 1},
        {"secret_exposure_count": 1},
        {"post_worker_exec_count": 1},
        {"git_publication_effect_count": 1},
        {"git_metadata_write_count": 1},
        {"control_input_write_count": 1},
        {"task_command_exec_count": 1},
        {"host_write_outside_allocation_count": 1},
        {"writable_mount_set": ["/workspace", "/tmp"]},
    ],
)
def test_negative_effect_observer_rejects_every_forbidden_effect(updates: dict) -> None:
    with pytest.raises(Stage3EvidenceError):
        validate_external_negative_observation(
            _observer(**updates),
            expected_target="target.txt",
            allocation_root="/workspace",
            worker_stopped_receipt_sha256="a" * 64,
            expected_workspace_instance_id="workspace-stage3-001",
        )


@pytest.mark.parametrize("count", [0, 2])
def test_mutation_count_zero_or_two_is_rejected(count: int) -> None:
    mutation = SimpleNamespace(
        path="target.txt",
        replacement_text="after",
        expected_after_sha256=sha256_bytes(b"after"),
    )
    validated = SimpleNamespace(mutations=tuple(mutation for _ in range(count)))
    frozen = {"contract": {"task": {"allowed_paths": ["target.txt"], "protected_paths": []}}}
    with pytest.raises(Stage3RuntimeError, match="exactly one"):
        _revalidate_exact_mutation_scope(frozen_result=frozen, validated=validated)


@pytest.mark.parametrize(
    "path,allowed,protected",
    [
        ("outside.txt", ["target.txt"], []),
        ("target.txt", ["target.txt"], ["target.*"]),
        (".git/index", [".git/index"], []),
    ],
)
def test_out_of_allowed_protected_and_git_metadata_paths_are_rejected(path, allowed, protected) -> None:
    mutation = SimpleNamespace(
        path=path,
        replacement_text="after",
        expected_after_sha256=sha256_bytes(b"after"),
    )
    validated = SimpleNamespace(mutations=(mutation,))
    frozen = {"contract": {"task": {"allowed_paths": allowed, "protected_paths": protected}}}
    with pytest.raises(Stage3RuntimeError):
        _revalidate_exact_mutation_scope(frozen_result=frozen, validated=validated)


def test_non_regular_git_object_and_wrong_before_hash_are_rejected(tmp_path: Path) -> None:
    root, commit, tree, blob = make_loose_git_fixture(tmp_path)
    _, entries = verify_pinned_clean_workspace(
        root, repository="FJ899/fixture", expected_repository="FJ899/fixture", commit=commit, tree=tree
    )
    with pytest.raises(Stage3WorkspaceError, match="regular Git blob"):
        open_validated_target_readonly(
            root,
            path="target.txt",
            expected_before_sha256=sha256_bytes(b"before\n"),
            tree_entries={"target.txt": ("120000", blob)},
        )
    with pytest.raises(Stage3WorkspaceError, match="hash mismatch"):
        open_validated_target_readonly(
            root,
            path="target.txt",
            expected_before_sha256="0" * 64,
            tree_entries=entries,
        )


def test_target_identity_swap_between_validation_and_write_is_rejected(tmp_path: Path) -> None:
    root, commit, tree, _ = make_loose_git_fixture(tmp_path)
    _, entries = verify_pinned_clean_workspace(
        root, repository="FJ899/fixture", expected_repository="FJ899/fixture", commit=commit, tree=tree
    )
    fd, snap = open_validated_target_readonly(
        root, path="target.txt", expected_before_sha256=sha256_bytes(b"before\n"), tree_entries=entries
    )
    target = root / "target.txt"
    data = target.read_bytes()
    target.unlink()
    target.write_bytes(data)
    target.chmod(0o644)
    try:
        with pytest.raises(Stage3WorkspaceError, match="identity changed"):
            reopen_target_for_effect(root, path="target.txt", pre_effect=snap)
    finally:
        os.close(fd)


def _attestation_stdout(*, evidence_sha: str, profile: Stage3GenerationTrustProfile, request_sha: str) -> bytes:
    return json.dumps([
        {
            "verificationResult": {
                "statement": {
                    "predicateType": profile.accepted_predicate_type,
                    "subject": [{"name": "provider-generation-evidence.json", "digest": {"sha256": evidence_sha}}],
                    "predicate": {
                        "schema_version": "executor-stage3-generation-attestation-predicate/1.0",
                        "provider_generation_evidence_schema": "executor-provider-generation-evidence/1.0",
                        "provider_generation_evidence_sha256": evidence_sha,
                        "verification_request_sha256": request_sha,
                    },
                }
            }
        }
    ], separators=(",", ":")).encode()


def test_offline_attestation_verifier_pins_signer_digest_subject_and_hosted_runner(monkeypatch, tmp_path: Path) -> None:
    import executor.stage3_generation_trust as trust

    gh = tmp_path / "gh"
    gh.write_text("fixed verifier", encoding="utf-8")
    monkeypatch.setattr(trust, "_FIXED_GH", gh)
    profile = _profile()
    evidence_sha = "d" * 64
    request_sha = "e" * 64
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = list(argv)
        return SimpleNamespace(
            returncode=0,
            stdout=_attestation_stdout(evidence_sha=evidence_sha, profile=profile, request_sha=request_sha),
            stderr=b"",
        )

    monkeypatch.setattr(trust.subprocess, "run", fake_run)
    evidence = tmp_path / "evidence.json"
    bundle = tmp_path / "bundle.json"
    evidence.write_text("{}", encoding="utf-8")
    bundle.write_text("{}", encoding="utf-8")
    _verify_attestation_offline(
        evidence_path=evidence,
        bundle_path=bundle,
        evidence_sha256=evidence_sha,
        profile=profile,
        expected_request_sha256=request_sha,
    )
    argv = captured["argv"]
    assert argv[argv.index("--signer-digest") + 1] == profile.signer_digest
    assert argv[argv.index("--signer-workflow") + 1] == "FJ899/Executor/.github/workflows/stage3-generation-verifier-attestation.yml"
    assert "--deny-self-hosted-runners" in argv
    assert argv[argv.index("--predicate-type") + 1] == profile.accepted_predicate_type

    def wrong_subject(argv, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=_attestation_stdout(evidence_sha="f" * 64, profile=profile, request_sha=request_sha),
            stderr=b"",
        )

    monkeypatch.setattr(trust.subprocess, "run", wrong_subject)
    with pytest.raises(Stage3GenerationTrustError, match="subject digest"):
        _verify_attestation_offline(
            evidence_path=evidence,
            bundle_path=bundle,
            evidence_sha256=evidence_sha,
            profile=profile,
            expected_request_sha256=request_sha,
        )


def test_negative_effect_observer_rejects_wrong_workspace_identity() -> None:
    with pytest.raises(Stage3EvidenceError, match="workspace identity"):
        validate_external_negative_observation(
            _observer(workspace_instance_id="other-workspace"),
            expected_target="target.txt",
            allocation_root="/workspace",
            worker_stopped_receipt_sha256="a" * 64,
            expected_workspace_instance_id="workspace-stage3-001",
        )


def test_runtime_trust_profile_rejects_altered_root(monkeypatch, tmp_path: Path) -> None:
    import executor.stage3_generation_trust as trust
    root = Path(__file__).resolve().parents[1]
    original_policy = json.loads((root / "trust_profiles/stage3_generation_identity_policy.json").read_text())
    bad_root = tmp_path / "root.jsonl"
    bad_root.write_text('{"mediaType":"application/vnd.dev.sigstore.trustedroot+json;version=0.1"}\n', encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_bytes(canonical_json(original_policy).encode())
    monkeypatch.setattr(trust, "_TRUST_ROOT", bad_root)
    monkeypatch.setattr(trust, "_IDENTITY_POLICY", policy)
    with pytest.raises(Stage3GenerationTrustError, match="trusted-root content hash"):
        trust._load_profile()


def test_evidence_self_hash_tampering_is_rejected() -> None:
    frozen, stage2, proposal, evidence = _provider_inputs()
    raw = canonical_json(evidence).encode()
    evidence["evidence_artifact_sha256"] = "f" * 64
    tampered = canonical_json(evidence).encode()
    assert raw != tampered
    with pytest.raises(Stage3GenerationTrustError, match="self hash"):
        _validate_evidence_semantics(
            evidence,
            raw=tampered,
            profile=_profile(),
            frozen_result=frozen,
            stage2_result=stage2,
            proposal=proposal,
        )


def test_evidence_schema_rejects_widened_terminal_claims() -> None:
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/stage3_evidence.schema.json").read_text())
    allowed = set(schema["$defs"]["effect"]["properties"]["terminal_status"]["enum"])
    assert allowed == {"FAIL", "UNKNOWN", "MUTATION_APPLIED_REVIEW_REQUIRED"}
    assert {"PASS", "TASK_FIXED", "TEST_PASS", "MERGE_READY"}.isdisjoint(allowed)
