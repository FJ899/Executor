from __future__ import annotations

import hashlib
import inspect
import json
import os
import stat
import struct
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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
    Stage3WorkspaceError,
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
        int(info.st_ctime), 0, int(info.st_mtime), 0,
        info.st_dev & 0xFFFFFFFF, info.st_ino & 0xFFFFFFFF,
        mode, info.st_uid, info.st_gid, info.st_size,
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


def test_runtime_has_no_caller_verifier_or_pilot_runtime_surface() -> None:
    assert str(inspect.signature(Stage3MutationRuntime)) == "()"
    assert Stage3MutationRuntime.__bases__ == (object,)
    source = inspect.getsource(Stage3MutationRuntime.execute)
    assert "generation_verifier" not in source
    assert "precondition_argv" not in source
    assert "postcondition_argv" not in source
    assert "regression_argv" not in source
    assert {item.value for item in Stage3TerminalStatus} == {
        "BLOCK", "FAIL", "UNKNOWN", "MUTATION_APPLIED_REVIEW_REQUIRED"
    }


def test_pinned_workspace_and_descriptor_worker_apply_exact_one_file(tmp_path: Path) -> None:
    root, commit, tree, _ = make_loose_git_fixture(tmp_path)
    identity, entries = verify_pinned_clean_workspace(
        root,
        repository="FJ899/fixture",
        expected_repository="FJ899/fixture",
        commit=commit,
        tree=tree,
    )
    assert identity.commit == commit and identity.tree == tree
    pre_repo = build_repository_manifest(root)
    pre_git = build_git_manifest(root)
    pre_git_ids = git_manifest_identities(pre_git)
    before = (root / "target.txt").read_bytes()
    replacement = b"after exact bytes\n"
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
            expected_after_sha256=sha256_bytes(replacement),
            pre_effect=pre_target,
        )
    finally:
        os.close(write_fd)
    assert count == len(replacement)
    assert observed.content_sha256 == sha256_bytes(replacement)
    post_repo = build_repository_manifest(root)
    post_git = build_git_manifest(root)
    assert changed_paths(pre_repo, post_repo) == ("target.txt",)
    assert pre_git.root_sha256 == post_git.root_sha256
    assert pre_git_ids == git_manifest_identities(post_git)
    assert stat.S_IMODE((root / "target.txt").stat().st_mode) == 0o644


def test_human_authority_is_exact_and_replay_safe(tmp_path: Path) -> None:
    now = datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)
    frozen, value = _authorization(now=now)
    authority = _validate_auth(frozen, value, now=now)
    assert authority_is_unused(tmp_path, authority.authorization_id)
    receipt = consume_authority_once(
        control_root=tmp_path,
        authority=authority,
        effect_binding_sha256="9" * 64,
    )
    assert receipt.state == "CONSUMED_PENDING"
    assert not authority_is_unused(tmp_path, authority.authorization_id)
    with pytest.raises(Stage3AuthorityError, match="consumed|replay"):
        consume_authority_once(
            control_root=tmp_path,
            authority=authority,
            effect_binding_sha256="9" * 64,
        )


def test_stage3_schemas_are_closed_and_canonical() -> None:
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "schemas/stage3_effect_authorization.schema.json",
        "schemas/stage3_evidence.schema.json",
    ):
        raw = (root / relative).read_bytes()
        value = json.loads(raw)
        assert raw == canonical_json(value).encode("utf-8")
        assert value["type"] == "object"
        assert value["additionalProperties"] is False


def test_human_authority_rejects_expired_wrong_environment_and_tampered_field(tmp_path: Path) -> None:
    now = datetime(2026, 8, 27, 19, 0, tzinfo=timezone.utc)
    frozen, value = _authorization(now=now)

    expired = dict(value)
    expired["issued_at"] = (now - timedelta(minutes=20)).isoformat().replace("+00:00", "Z")
    expired["expires_at"] = (now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    material = dict(expired); material.pop("authorization_payload_sha256")
    expired["authorization_payload_sha256"] = hashlib.sha256(canonical_json(material).encode()).hexdigest()
    with pytest.raises(Stage3AuthorityError, match="expired"):
        _validate_auth(frozen, expired, now=now)

    wrong_env = dict(value)
    wrong_env["bounded_environment_sha256"] = "d" * 64
    material = dict(wrong_env); material.pop("authorization_payload_sha256")
    wrong_env["authorization_payload_sha256"] = hashlib.sha256(canonical_json(material).encode()).hexdigest()
    with pytest.raises(Stage3AuthorityError, match="environment"):
        _validate_auth(frozen, wrong_env, now=now)

    tampered = dict(value)
    tampered["mutation_path"] = "other.txt"
    with pytest.raises(Stage3AuthorityError):
        _validate_auth(frozen, tampered, now=now)
