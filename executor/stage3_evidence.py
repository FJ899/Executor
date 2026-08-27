from __future__ import annotations

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executor.github_trust import canonical_json


class Stage3EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class Manifest:
    kind: str
    entries: tuple[dict[str, Any], ...]
    root_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "executor-stage3-manifest/1.0",
            "kind": self.kind,
            "entries": [dict(item) for item in self.entries],
            "root_sha256": self.root_sha256,
        }


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def _entry_for_path(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    info = path.lstat()
    mode = stat.S_IMODE(info.st_mode)
    common: dict[str, Any] = {
        "path": relative,
        "mode": mode,
        "uid": info.st_uid,
        "gid": info.st_gid,
        "nlink": info.st_nlink,
        "size": info.st_size,
    }
    if stat.S_ISREG(info.st_mode):
        data = path.read_bytes()
        common.update({"type": "regular", "content_sha256": sha256_bytes(data)})
    elif stat.S_ISDIR(info.st_mode):
        common.update({"type": "directory", "content_sha256": None})
    elif stat.S_ISLNK(info.st_mode):
        target = os.readlink(path)
        common.update(
            {
                "type": "symlink",
                "content_sha256": sha256_bytes(target.encode("utf-8", "surrogateescape")),
            }
        )
    elif stat.S_ISFIFO(info.st_mode):
        common.update({"type": "fifo", "content_sha256": None})
    elif stat.S_ISSOCK(info.st_mode):
        common.update({"type": "socket", "content_sha256": None})
    elif stat.S_ISCHR(info.st_mode):
        common.update({"type": "char-device", "content_sha256": None, "rdev": info.st_rdev})
    elif stat.S_ISBLK(info.st_mode):
        common.update({"type": "block-device", "content_sha256": None, "rdev": info.st_rdev})
    else:
        common.update({"type": "other", "content_sha256": None})
    return common


def _walk_manifest(root: Path, *, skip_top_level_git: bool) -> tuple[dict[str, Any], ...]:
    if not root.is_dir():
        raise Stage3EvidenceError(f"manifest root is not a directory: {root}")
    paths: list[str] = []
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        rel_current = current_path.relative_to(root)
        if rel_current == Path(".") and skip_top_level_git and ".git" in dirnames:
            dirnames.remove(".git")
        for name in sorted(dirnames + filenames):
            rel = (rel_current / name).as_posix()
            if rel.startswith("./"):
                rel = rel[2:]
            paths.append(rel)
    entries = tuple(_entry_for_path(root, relative) for relative in sorted(set(paths)))
    return entries


def build_repository_manifest(repository_root: str | Path) -> Manifest:
    root = Path(repository_root)
    entries = _walk_manifest(root, skip_top_level_git=True)
    payload = {
        "schema_version": "executor-stage3-manifest/1.0",
        "kind": "repository-plane-excluding-git",
        "entries": list(entries),
    }
    return Manifest(payload["kind"], entries, sha256_json(payload))


def build_git_manifest(repository_root: str | Path) -> Manifest:
    root = Path(repository_root) / ".git"
    entries = _walk_manifest(root, skip_top_level_git=False)
    payload = {
        "schema_version": "executor-stage3-manifest/1.0",
        "kind": "git-metadata",
        "entries": list(entries),
    }
    return Manifest(payload["kind"], entries, sha256_json(payload))


def git_manifest_identities(manifest: Manifest) -> dict[str, str]:
    if manifest.kind != "git-metadata":
        raise Stage3EvidenceError("Git identities require the git-metadata manifest")
    entries = {item["path"]: item for item in manifest.entries}
    head = entries.get("HEAD")
    index = entries.get("index")
    if not isinstance(head, dict) or head.get("type") != "regular":
        raise Stage3EvidenceError("Git manifest does not contain regular HEAD")
    if not isinstance(index, dict) or index.get("type") != "regular":
        raise Stage3EvidenceError("Git manifest does not contain regular index")
    ref_entries = [
        item
        for item in manifest.entries
        if item["path"] == "packed-refs" or item["path"].startswith("refs/")
    ]
    return {
        "head_sha256": head["content_sha256"],
        "index_sha256": index["content_sha256"],
        "refs_sha256": sha256_json(ref_entries),
    }


def changed_paths(before: Manifest, after: Manifest) -> tuple[str, ...]:
    before_by_path = {item["path"]: item for item in before.entries}
    after_by_path = {item["path"]: item for item in after.entries}
    changed = {
        path
        for path in set(before_by_path) | set(after_by_path)
        if before_by_path.get(path) != after_by_path.get(path)
    }
    return tuple(sorted(changed))


def canonical_patch_identity(
    *,
    path: str,
    before_sha256: str,
    after_sha256: str,
    before_mode: int,
    after_mode: int,
    replacement_byte_length: int,
) -> str:
    payload = {
        "schema_version": "executor-stage3-patch-identity/1.0",
        "path": path,
        "before_sha256": before_sha256,
        "after_sha256": after_sha256,
        "before_mode": before_mode,
        "after_mode": after_mode,
        "replacement_byte_length": replacement_byte_length,
    }
    return sha256_json(payload)


def durable_write_json(path: str | Path, value: dict[str, Any], *, exclusive: bool = True) -> str:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    raw = canonical_json(value).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_CLOEXEC
    flags |= os.O_EXCL if exclusive else os.O_TRUNC
    fd = os.open(destination, flags, 0o600)
    try:
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            if written <= 0:
                raise Stage3EvidenceError("short write while persisting Stage-3 receipt")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)
    parent_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return sha256_bytes(raw)


def read_canonical_json(path: str | Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8")
        value = json.loads(text)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Stage3EvidenceError(f"{label} is not UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise Stage3EvidenceError(f"{label} must be a JSON object")
    canonical = canonical_json(value).encode("utf-8")
    if raw != canonical:
        raise Stage3EvidenceError(f"{label} is not canonical JSON")
    return value, raw


def validate_external_negative_observation(
    value: dict[str, Any], *, expected_target: str, allocation_root: str, worker_stopped_receipt_sha256: str, expected_workspace_instance_id: str
) -> str:
    expected = {
        "schema_version",
        "observer_id",
        "workspace_instance_id",
        "repository_write_targets",
        "writable_mount_set",
        "network_effect_count",
        "secret_exposure_count",
        "post_worker_exec_count",
        "git_publication_effect_count",
        "git_metadata_write_count",
        "control_input_write_count",
        "task_command_exec_count",
        "host_write_outside_allocation_count",
        "worker_stopped_receipt_sha256",
        "raw_observation_sha256",
    }
    if set(value) != expected:
        raise Stage3EvidenceError("external negative observation has invalid fields")
    if value.get("schema_version") != "executor-stage3-host-observer/1.0":
        raise Stage3EvidenceError("external negative observation schema mismatch")
    if not isinstance(value.get("observer_id"), str) or not value["observer_id"]:
        raise Stage3EvidenceError("external observer identity is missing")
    if value.get("worker_stopped_receipt_sha256") != worker_stopped_receipt_sha256:
        raise Stage3EvidenceError("external observer is not bound to the post-worker receipt")
    if value.get("workspace_instance_id") != expected_workspace_instance_id:
        raise Stage3EvidenceError("external observer workspace identity mismatch")
    targets = value.get("repository_write_targets")
    if targets != [expected_target]:
        raise Stage3EvidenceError("external observer did not record the exact one-path write set")
    mounts = value.get("writable_mount_set")
    if not isinstance(mounts, list) or not all(isinstance(item, str) for item in mounts):
        raise Stage3EvidenceError("external observer writable mount set is invalid")
    for item in mounts:
        if item != allocation_root and not item.startswith(allocation_root.rstrip("/") + "/"):
            raise Stage3EvidenceError("external observer found a writable mount outside allocation")
    for field in (
        "network_effect_count",
        "secret_exposure_count",
        "post_worker_exec_count",
        "git_publication_effect_count",
        "git_metadata_write_count",
        "control_input_write_count",
        "task_command_exec_count",
        "host_write_outside_allocation_count",
    ):
        if value.get(field) != 0:
            raise Stage3EvidenceError(f"external observer found forbidden effect: {field}")
    digest = value.get("raw_observation_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise Stage3EvidenceError("external observer raw digest is invalid")
    return sha256_json(value)


def evidence_bundle_sha256(bundle: dict[str, Any]) -> str:
    return sha256_json(bundle)
