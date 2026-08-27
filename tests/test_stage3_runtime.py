from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import struct
import tempfile
import unittest
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from executor.github_trust import canonical_json
from executor.stage3_authority import (
    AUTH_HASH_CONSTRUCTION,
    AUTH_SCHEMA,
    P1_STAGE3_ID,
    P1_STAGE3_SHA256,
    STAGE3_ACTION,
    Stage3AuthorityError,
    authority_is_unused,
    consume_authority_once,
    validate_human_stage3_effect_authorization,
)
from executor.stage3_evidence import (
    build_git_manifest,
    build_repository_manifest,
    changed_paths,
    git_manifest_identities,
    sha256_bytes,
)
from executor.stage3_runtime import Stage3MutationRuntime, Stage3TerminalStatus
from executor.stage3_workspace import (
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


def make_loose_git_fixture(tmp_path: Path, content: bytes = b"before\n") -> tuple[Path, str, str, str]:
    root = tmp_path / "repo"
    git = root / ".git"
    (git / "objects").mkdir(parents=True)
    target = root / "target.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    target.chmod(0o644)
    blob = _git_object(git, "blob", content)
    tree_body = b"100644 target.txt\0" + bytes.fromhex(blob)
    tree = _git_object(git, "tree", tree_body)
    commit_body = (
        f"tree {tree}\nauthor Stage3 <stage3@example.invalid> 0 +0000\n"
        f"committer Stage3 <stage3@example.invalid> 0 +0000\n\nfixture\n"
    ).encode("utf-8")
    commit = _git_object(git, "commit", commit_body)
    (git / "HEAD").write_text(commit + "\n", encoding="ascii")
    _write_index(git, root, "target.txt", blob)
    return root, commit, tree, blob


def _authorization(*, now: datetime, environment_sha: str = "e" * 64) -> tuple[dict, dict]:
    frozen = {
        "decision_evidence": {
            "actor": {"login": "human", "id": 7},
            "evidence_ref": "github:comment:node:hash",
        }
    }
    value = {
        "schema_version": AUTH_SCHEMA,
        "authorization_id": "auth-stage3-001",
        "human_principal": {"provider": "GITHUB", "login": "human", "id": 7},
        "human_principal_evidence_ref": "github:comment:node:hash",
        "frozen_task_contract_id": P1_STAGE3_ID,
        "frozen_task_contract_sha256": P1_STAGE3_SHA256,
        "stage2_terminal_result_sha256": "1" * 64,
        "repository": "FJ899/fixture",
        "source_commit": "2" * 40,
        "source_tree": "3" * 40,
        "proposal_id": "proposal-stage3-001",
        "proposal_payload_sha256": "4" * 64,
        "mutation_path": "target.txt",
        "before_sha256": "5" * 64,
        "after_sha256": "6" * 64,
        "provider_generation_binding_sha256": "7" * 64,
        "runtime_trust_bundle_sha256": "8" * 64,
        "bounded_environment_sha256": environment_sha,
        "workspace_instance_id": "workspace-stage3-001",
        "action": STAGE3_ACTION,
        "issued_at": (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        "expires_at": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        "authorization_hash_construction": AUTH_HASH_CONSTRUCTION,
        "authorization_payload_sha256": "0" * 64,
    }
    material = dict(value)
    material.pop("authorization_payload_sha256")
    value["authorization_payload_sha256"] = hashlib.sha256(
        canonical_json(material).encode("utf-8")
    ).hexdigest()
    return frozen, value


def _validate_auth(frozen: dict, value: dict, *, now: datetime):
    return validate_human_stage3_effect_authorization(
        value,
        frozen_result=frozen,
        stage2_terminal_result_sha256="1" * 64,
        repository="FJ899/fixture",
        source_commit="2" * 40,
        source_tree="3" * 40,
        proposal_id="proposal-stage3-001",
        proposal_payload_sha256="4" * 64,
        mutation_path="target.txt",
        before_sha256="5" * 64,
        after_sha256="6" * 64,
        provider_generation_binding_sha256="7" * 64,
        runtime_trust_bundle_sha256="8" * 64,
        bounded_environment_sha256="e" * 64,
        workspace_instance_id="workspace-stage3-001",
        now=now,
    )


class Stage3RuntimeTests(unittest.TestCase):
    def test_runtime_has_no_caller_verifier_or_pilot_runtime_surface_and_terminal_semantics(self) -> None:
        self.assertEqual(str(inspect.signature(Stage3MutationRuntime)), "()")
        self.assertEqual(Stage3MutationRuntime.__bases__, (object,))
        source = inspect.getsource(Stage3MutationRuntime.execute)
        for forbidden in (
            "generation_verifier",
            "precondition_argv",
            "postcondition_argv",
            "regression_argv",
        ):
            self.assertNotIn(forbidden, source)
        self.assertEqual(
            {item.value for item in Stage3TerminalStatus},
            {"BLOCK", "FAIL", "UNKNOWN", "MUTATION_APPLIED_REVIEW_REQUIRED"},
        )
        self.assertNotIn("PASS", {item.value for item in Stage3TerminalStatus})
        self.assertNotIn("RETRY", {item.value for item in Stage3TerminalStatus})

    def test_exact_one_file_replacement_exact_after_hash_one_changed_path_and_git_metadata_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, commit, tree, _ = make_loose_git_fixture(Path(temp_dir))
            identity, entries = verify_pinned_clean_workspace(
                root,
                repository="FJ899/fixture",
                expected_repository="FJ899/fixture",
                commit=commit,
                tree=tree,
            )
            self.assertEqual(identity.commit, commit)
            self.assertEqual(identity.tree, tree)
            pre_repo = build_repository_manifest(root)
            pre_git = build_git_manifest(root)
            pre_git_ids = git_manifest_identities(pre_git)
            before = (root / "target.txt").read_bytes()
            replacement = b"after exact bytes\n"
            expected_after = sha256_bytes(replacement)
            read_fd, pre_target = open_validated_target_readonly(
                root,
                path="target.txt",
                expected_before_sha256=sha256_bytes(before),
                tree_entries=entries,
            )
            os.close(read_fd)
            write_fd = reopen_target_for_effect(root, path="target.txt", pre_effect=pre_target)
            try:
                observed, count = apply_exact_descriptor_replacement(
                    write_fd,
                    replacement=replacement,
                    expected_after_sha256=expected_after,
                    pre_effect=pre_target,
                )
            finally:
                os.close(write_fd)
            self.assertEqual(count, len(replacement))
            self.assertEqual(observed.content_sha256, expected_after)
            self.assertEqual(sha256_bytes((root / "target.txt").read_bytes()), expected_after)
            post_repo = build_repository_manifest(root)
            post_git = build_git_manifest(root)
            self.assertEqual(changed_paths(pre_repo, post_repo), ("target.txt",))
            self.assertEqual(pre_git.root_sha256, post_git.root_sha256)
            self.assertEqual(pre_git_ids, git_manifest_identities(post_git))
            self.assertEqual(stat.S_IMODE((root / "target.txt").stat().st_mode), 0o644)

    def test_missing_human_authority_evidence_is_rejected(self) -> None:
        now = datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)
        _, value = _authorization(now=now)
        with self.assertRaisesRegex(Stage3AuthorityError, "evidence is missing"):
            _validate_auth({}, value, now=now)

    def test_mismatched_human_authority_environment_is_rejected(self) -> None:
        now = datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)
        frozen, value = _authorization(now=now)
        mismatched = dict(value)
        mismatched["bounded_environment_sha256"] = "d" * 64
        material = dict(mismatched)
        material.pop("authorization_payload_sha256")
        mismatched["authorization_payload_sha256"] = hashlib.sha256(
            canonical_json(material).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(Stage3AuthorityError, "environment"):
            _validate_auth(frozen, mismatched, now=now)

    def test_replayed_human_authority_is_rejected_and_second_write_authority_is_not_minted(self) -> None:
        now = datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)
        frozen, value = _authorization(now=now)
        authority = _validate_auth(frozen, value, now=now)
        with tempfile.TemporaryDirectory() as temp_dir:
            control_root = Path(temp_dir)
            self.assertTrue(authority_is_unused(control_root, authority.authorization_id))
            receipt = consume_authority_once(
                control_root=control_root,
                authority=authority,
                effect_binding_sha256="9" * 64,
            )
            self.assertEqual(receipt.state, "CONSUMED_PENDING")
            self.assertFalse(authority_is_unused(control_root, authority.authorization_id))
            with self.assertRaisesRegex(Stage3AuthorityError, "consumed|replay"):
                consume_authority_once(
                    control_root=control_root,
                    authority=authority,
                    effect_binding_sha256="9" * 64,
                )
            self.assertFalse(authority_is_unused(control_root, authority.authorization_id))

    def test_expired_and_tampered_human_authority_is_rejected(self) -> None:
        now = datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)
        frozen, value = _authorization(now=now)
        expired = dict(value)
        expired["issued_at"] = (now - timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
        expired["expires_at"] = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        material = dict(expired)
        material.pop("authorization_payload_sha256")
        expired["authorization_payload_sha256"] = hashlib.sha256(
            canonical_json(material).encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(Stage3AuthorityError, "expired"):
            _validate_auth(frozen, expired, now=now)

        tampered = dict(value)
        tampered["mutation_path"] = "other.txt"
        with self.assertRaises(Stage3AuthorityError):
            _validate_auth(frozen, tampered, now=now)

    def test_stage3_schemas_are_closed_and_canonical(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for relative in (
            "schemas/stage3_effect_authorization.schema.json",
            "schemas/stage3_evidence.schema.json",
        ):
            raw = (root / relative).read_bytes()
            value = json.loads(raw)
            self.assertEqual(raw, canonical_json(value).encode("utf-8"))
            self.assertEqual(value["type"], "object")
            self.assertIs(value["additionalProperties"], False)


if __name__ == "__main__":
    unittest.main()
