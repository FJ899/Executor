from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import platform
import signal
import socket
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.github_trust import canonical_json
from executor.stage3_evidence import (
    Stage3EvidenceError,
    sha256_bytes,
    sha256_json,
    validate_external_negative_observation,
)
from executor.stage3_generation_trust import (
    Stage3GenerationTrustError,
    Stage3GenerationTrustProfile,
    _expected_request,
    _validate_evidence_semantics,
    _verify_attestation_offline,
)
from executor.stage3_runtime import Stage3RuntimeError, _revalidate_exact_mutation_scope
from executor.stage3_workspace import (
    Stage3WorkspaceError,
    _install_descriptor_only_seccomp,
    apply_exact_descriptor_replacement,
    open_validated_target_readonly,
    reopen_target_for_effect,
    verify_pinned_clean_workspace,
)


def _git_object(git_dir: Path, kind: str, body: bytes) -> str:
    raw = f"{kind} {len(body)}\0".encode("ascii") + body
    oid = hashlib.sha1(raw).hexdigest()
    path = git_dir / "objects" / oid[:2] / oid[2:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zlib.compress(raw))
    return oid


def _write_index(git_dir: Path, worktree: Path, path: str, oid: str, mode: int = 0o100644) -> None:
    info = (worktree / path).lstat()
    name = path.encode("utf-8")
    flags = min(len(name), 0xFFF)
    fields = (
        int(info.st_ctime),
        0,
        int(info.st_mtime),
        0,
        info.st_dev & 0xFFFFFFFF,
        info.st_ino & 0xFFFFFFFF,
        mode,
        info.st_uid,
        info.st_gid,
        info.st_size,
    )
    entry = struct.pack(">10I20sH", *fields, bytes.fromhex(oid), flags) + name + b"\0"
    entry += b"\0" * ((8 - (len(entry) % 8)) % 8)
    body = b"DIRC" + struct.pack(">II", 2, 1) + entry
    (git_dir / "index").write_bytes(body + hashlib.sha1(body).digest())


def _make_loose_git_fixture(tmp_path: Path, content: bytes = b"before\n") -> tuple[Path, str, str, str]:
    root = tmp_path / "repo"
    git = root / ".git"
    (git / "objects").mkdir(parents=True)
    target = root / "target.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    target.chmod(0o644)
    blob = _git_object(git, "blob", content)
    tree = _git_object(git, "tree", b"100644 target.txt\0" + bytes.fromhex(blob))
    commit_body = (
        f"tree {tree}\nauthor Stage3 <stage3@example.invalid> 0 +0000\n"
        f"committer Stage3 <stage3@example.invalid> 0 +0000\n\nfixture\n"
    ).encode("utf-8")
    commit = _git_object(git, "commit", commit_body)
    (git / "HEAD").write_text(commit + "\n", encoding="ascii")
    _write_index(git, root, "target.txt", blob)
    return root, commit, tree, blob


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
    value["evidence_artifact_sha256"] = sha256_json(value)
    return canonical_json(value).encode("utf-8")


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


def _attestation_stdout(*, evidence_sha: str, profile: Stage3GenerationTrustProfile, request_sha: str) -> bytes:
    return json.dumps(
        [
            {
                "verificationResult": {
                    "statement": {
                        "predicateType": profile.accepted_predicate_type,
                        "subject": [
                            {
                                "name": "provider-generation-evidence.json",
                                "digest": {"sha256": evidence_sha},
                            }
                        ],
                        "predicate": {
                            "schema_version": "executor-stage3-generation-attestation-predicate/1.0",
                            "provider_generation_evidence_schema": "executor-provider-generation-evidence/1.0",
                            "provider_generation_evidence_sha256": evidence_sha,
                            "verification_request_sha256": request_sha,
                        },
                    }
                }
            }
        ],
        separators=(",", ":"),
    ).encode()


class Stage3AdversarialTests(unittest.TestCase):
    def test_frozen_reusable_verifier_workflow_is_closed_and_pinned(self) -> None:
        root = Path(__file__).resolve().parents[1]
        raw = (root / ".github/workflows/stage3-generation-verifier-attestation.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("on:\n  workflow_call:", raw)
        for forbidden in (
            "\n  push:",
            "\n  pull_request:",
            "\n  pull_request_target:",
            "\n  workflow_dispatch:",
            "\n  repository_dispatch:",
            "\n  schedule:",
            "\n  issue_comment:",
        ):
            self.assertNotIn(forbidden, raw)
        self.assertIn("permissions:\n  contents: read\n  id-token: write\n  attestations: write", raw)
        self.assertIn("runs-on: ubuntu-latest", raw)
        self.assertIn("actions/attest@f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6", raw)
        self.assertNotIn("actions/checkout", raw)
        self.assertIn("self-hosted runner is forbidden", raw)
        self.assertIn("api.openai.com/v1", raw)
        self.assertIn("job.workflow_repository", raw)
        self.assertIn("job.workflow_file_path", raw)
        self.assertIn("job.workflow_sha", raw)

    def test_caller_verifier_and_caller_evidence_attack_has_no_runtime_trust_path(self) -> None:
        from executor import stage3_generation_trust as trust

        sig = inspect.signature(trust.verify_provider_generation_binding)
        self.assertNotIn("verifier", sig.parameters)
        self.assertNotIn("trust_root", sig.parameters)
        self.assertNotIn("identity_policy", sig.parameters)
        source = inspect.getsource(trust.verify_provider_generation_binding)
        self.assertIn("_load_profile()", source)
        self.assertIn("_verify_attestation_offline", source)

    def test_provider_evidence_mismatch_is_rejected(self) -> None:
        bad_values = (
            ("provider_record_id", "resp_other"),
            ("response_sha256", "f" * 64),
            ("verifier_workflow_source_commit", "d" * 40),
            ("verifier_reusable_workflow_path", ".github/workflows/upload-download.yml"),
            ("attestation_predicate_type", "https://example.invalid/wrong"),
        )
        for field, bad in bad_values:
            with self.subTest(field=field):
                frozen, stage2, proposal, evidence = _provider_inputs()
                evidence[field] = bad
                raw = _rehash_evidence(evidence)
                parsed = json.loads(raw)
                with self.assertRaises(Stage3GenerationTrustError):
                    _validate_evidence_semantics(
                        parsed,
                        raw=raw,
                        profile=_profile(),
                        frozen_result=frozen,
                        stage2_result=stage2,
                        proposal=proposal,
                    )

    def test_invalid_target_surfaces_hardlink_symlink_and_missing_are_rejected(self) -> None:
        for case in ("hardlink", "symlink", "nonexistent"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                root, commit, tree, _ = _make_loose_git_fixture(Path(temp_dir))
                _, entries = verify_pinned_clean_workspace(
                    root,
                    repository="FJ899/fixture",
                    expected_repository="FJ899/fixture",
                    commit=commit,
                    tree=tree,
                )
                target = root / "target.txt"
                if case == "hardlink":
                    os.link(target, root / "alias.txt")
                elif case == "symlink":
                    victim = root / "victim.txt"
                    victim.write_text("victim", encoding="utf-8")
                    target.unlink()
                    target.symlink_to(victim.name)
                else:
                    target.unlink()
                with self.assertRaises(Stage3WorkspaceError):
                    open_validated_target_readonly(
                        root,
                        path="target.txt",
                        expected_before_sha256=sha256_bytes(b"before\n"),
                        tree_entries=entries,
                    )

    def test_dirty_wrong_source_and_replacement_after_hash_mismatch_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, commit, tree, _ = _make_loose_git_fixture(Path(temp_dir))
            (root / "extra.txt").write_text("dirty", encoding="utf-8")
            with self.assertRaisesRegex(Stage3WorkspaceError, "clean"):
                verify_pinned_clean_workspace(
                    root,
                    repository="FJ899/fixture",
                    expected_repository="FJ899/fixture",
                    commit=commit,
                    tree=tree,
                )
            (root / "extra.txt").unlink()
            with self.assertRaises(Stage3WorkspaceError):
                verify_pinned_clean_workspace(
                    root,
                    repository="wrong/repo",
                    expected_repository="FJ899/fixture",
                    commit=commit,
                    tree=tree,
                )
            _, entries = verify_pinned_clean_workspace(
                root,
                repository="FJ899/fixture",
                expected_repository="FJ899/fixture",
                commit=commit,
                tree=tree,
            )
            fd, snapshot = open_validated_target_readonly(
                root,
                path="target.txt",
                expected_before_sha256=sha256_bytes(b"before\n"),
                tree_entries=entries,
            )
            os.close(fd)
            write_fd = os.open(root / "target.txt", os.O_RDWR)
            try:
                with self.assertRaisesRegex(Stage3WorkspaceError, "after hash"):
                    apply_exact_descriptor_replacement(
                        write_fd,
                        replacement=b"not the declared after bytes",
                        expected_after_sha256="0" * 64,
                        pre_effect=snapshot,
                    )
            finally:
                os.close(write_fd)

    def _assert_seccomp_kills(self, kind: str) -> None:
        if platform.system() != "Linux" or platform.machine() not in {"x86_64", "AMD64"}:
            self.skipTest("Stage-3 worker environment is Linux x86_64")
        status = _run_forbidden_syscall(kind)
        self.assertTrue(os.WIFSIGNALED(status), f"{kind} did not terminate by signal: {status}")
        self.assertEqual(os.WTERMSIG(status), signal.SIGSYS)

    def test_seccomp_forbidden_open_syscall_is_killed(self) -> None:
        self._assert_seccomp_kills("open")

    def test_seccomp_forbidden_socket_syscall_is_killed(self) -> None:
        self._assert_seccomp_kills("socket")

    def test_seccomp_forbidden_execve_syscall_is_killed(self) -> None:
        self._assert_seccomp_kills("execve")

    def test_seccomp_forbidden_unlink_syscall_is_killed(self) -> None:
        self._assert_seccomp_kills("unlink")

    def test_forbidden_network_secret_exec_publication_and_other_negative_effects_are_rejected(self) -> None:
        forbidden_updates = (
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
        )
        for updates in forbidden_updates:
            with self.subTest(updates=updates), self.assertRaises(Stage3EvidenceError):
                validate_external_negative_observation(
                    _observer(**updates),
                    expected_target="target.txt",
                    allocation_root="/workspace",
                    worker_stopped_receipt_sha256="a" * 64,
                    expected_workspace_instance_id="workspace-stage3-001",
                )

    def test_negative_effect_observer_wrong_workspace_identity_is_rejected(self) -> None:
        with self.assertRaisesRegex(Stage3EvidenceError, "workspace identity"):
            validate_external_negative_observation(
                _observer(workspace_instance_id="other-workspace"),
                expected_target="target.txt",
                allocation_root="/workspace",
                worker_stopped_receipt_sha256="a" * 64,
                expected_workspace_instance_id="workspace-stage3-001",
            )

    def test_mutation_count_zero_or_two_is_rejected(self) -> None:
        mutation = SimpleNamespace(
            path="target.txt",
            replacement_text="after",
            expected_after_sha256=sha256_bytes(b"after"),
        )
        frozen = {"contract": {"task": {"allowed_paths": ["target.txt"], "protected_paths": []}}}
        for count in (0, 2):
            with self.subTest(count=count), self.assertRaisesRegex(Stage3RuntimeError, "exactly one"):
                _revalidate_exact_mutation_scope(
                    frozen_result=frozen,
                    validated=SimpleNamespace(mutations=tuple(mutation for _ in range(count))),
                )

    def test_out_of_allowed_protected_and_git_metadata_paths_are_rejected(self) -> None:
        cases = (
            ("outside.txt", ["target.txt"], []),
            ("target.txt", ["target.txt"], ["target.*"]),
            (".git/index", [".git/index"], []),
        )
        for path, allowed, protected in cases:
            mutation = SimpleNamespace(
                path=path,
                replacement_text="after",
                expected_after_sha256=sha256_bytes(b"after"),
            )
            frozen = {"contract": {"task": {"allowed_paths": allowed, "protected_paths": protected}}}
            with self.subTest(path=path), self.assertRaises(Stage3RuntimeError):
                _revalidate_exact_mutation_scope(
                    frozen_result=frozen,
                    validated=SimpleNamespace(mutations=(mutation,)),
                )

    def test_target_identity_swap_between_validation_and_write_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, commit, tree, _ = _make_loose_git_fixture(Path(temp_dir))
            _, entries = verify_pinned_clean_workspace(
                root,
                repository="FJ899/fixture",
                expected_repository="FJ899/fixture",
                commit=commit,
                tree=tree,
            )
            fd, snapshot = open_validated_target_readonly(
                root,
                path="target.txt",
                expected_before_sha256=sha256_bytes(b"before\n"),
                tree_entries=entries,
            )
            target = root / "target.txt"
            data = target.read_bytes()
            target.unlink()
            target.write_bytes(data)
            target.chmod(0o644)
            try:
                with self.assertRaisesRegex(Stage3WorkspaceError, "identity changed"):
                    reopen_target_for_effect(root, path="target.txt", pre_effect=snapshot)
            finally:
                os.close(fd)

    def test_offline_attestation_pins_signer_digest_and_rejects_wrong_subject(self) -> None:
        import executor.stage3_generation_trust as trust

        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            gh = temp / "gh"
            gh.write_text("fixed verifier", encoding="utf-8")
            profile = _profile()
            evidence_sha = "d" * 64
            request_sha = "e" * 64
            evidence = temp / "evidence.json"
            bundle = temp / "bundle.json"
            evidence.write_text("{}", encoding="utf-8")
            bundle.write_text("{}", encoding="utf-8")
            captured = {}

            def good_run(argv, **kwargs):
                captured["argv"] = list(argv)
                return SimpleNamespace(
                    returncode=0,
                    stdout=_attestation_stdout(
                        evidence_sha=evidence_sha,
                        profile=profile,
                        request_sha=request_sha,
                    ),
                    stderr=b"",
                )

            with patch.object(trust, "_FIXED_GH", gh), patch.object(trust.subprocess, "run", good_run):
                _verify_attestation_offline(
                    evidence_path=evidence,
                    bundle_path=bundle,
                    evidence_sha256=evidence_sha,
                    profile=profile,
                    expected_request_sha256=request_sha,
                )
            argv = captured["argv"]
            self.assertEqual(argv[argv.index("--signer-digest") + 1], profile.signer_digest)
            self.assertEqual(
                argv[argv.index("--signer-workflow") + 1],
                "FJ899/Executor/.github/workflows/stage3-generation-verifier-attestation.yml",
            )
            self.assertIn("--deny-self-hosted-runners", argv)
            self.assertEqual(
                argv[argv.index("--predicate-type") + 1],
                profile.accepted_predicate_type,
            )

            def wrong_subject(argv, **kwargs):
                return SimpleNamespace(
                    returncode=0,
                    stdout=_attestation_stdout(
                        evidence_sha="f" * 64,
                        profile=profile,
                        request_sha=request_sha,
                    ),
                    stderr=b"",
                )

            with patch.object(trust, "_FIXED_GH", gh), patch.object(trust.subprocess, "run", wrong_subject):
                with self.assertRaisesRegex(Stage3GenerationTrustError, "subject digest"):
                    _verify_attestation_offline(
                        evidence_path=evidence,
                        bundle_path=bundle,
                        evidence_sha256=evidence_sha,
                        profile=profile,
                        expected_request_sha256=request_sha,
                    )

    def test_runtime_trust_profile_rejects_altered_root(self) -> None:
        import executor.stage3_generation_trust as trust

        root = Path(__file__).resolve().parents[1]
        original_policy = json.loads(
            (root / "trust_profiles/stage3_generation_identity_policy.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            bad_root = temp / "root.jsonl"
            bad_root.write_text(
                '{"mediaType":"application/vnd.dev.sigstore.trustedroot+json;version=0.1"}\n',
                encoding="utf-8",
            )
            policy = temp / "policy.json"
            policy.write_bytes(canonical_json(original_policy).encode("utf-8"))
            with patch.object(trust, "_TRUST_ROOT", bad_root), patch.object(
                trust, "_IDENTITY_POLICY", policy
            ):
                with self.assertRaisesRegex(Stage3GenerationTrustError, "trusted-root content hash"):
                    trust._load_profile()

    def test_evidence_self_hash_tampering_is_rejected(self) -> None:
        frozen, stage2, proposal, evidence = _provider_inputs()
        raw = canonical_json(evidence).encode("utf-8")
        evidence["evidence_artifact_sha256"] = "f" * 64
        tampered = canonical_json(evidence).encode("utf-8")
        self.assertNotEqual(raw, tampered)
        with self.assertRaisesRegex(Stage3GenerationTrustError, "self hash"):
            _validate_evidence_semantics(
                evidence,
                raw=tampered,
                profile=_profile(),
                frozen_result=frozen,
                stage2_result=stage2,
                proposal=proposal,
            )


if __name__ == "__main__":
    unittest.main()
