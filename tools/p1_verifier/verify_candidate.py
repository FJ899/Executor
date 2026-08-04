#!/usr/bin/env python3
"""Trusted authoritative verifier for Executor P1 exact-ref observations.

This verifier is stdlib-only, is loaded from the trusted workflow commit, never
imports candidate code, and treats candidate tests/reports/PASS declarations as
observations only. Nested Docker authority is accepted only when a trusted host
collector supplies a complete, hash-bound operation ledger with immutable
create-time inspect records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IMAGE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
CONTAINER_ID_RE = re.compile(r"^[0-9a-f]{64}$")
URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


class VerificationError(RuntimeError):
    """Invalid trusted verifier invocation or malformed trusted configuration."""


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise VerificationError(f"missing JSON file: {path}") from None
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON in {path}: {exc}") from None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_env(home: Path) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
    }


def _run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_git_env(repo / ".trusted-empty-home"),
    )
    if completed.returncode != 0:
        raise VerificationError(
            f"git {' '.join(args)} failed in {repo}: {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def _safe_relative(path_text: str) -> bool:
    path = Path(path_text)
    return bool(path_text) and not path.is_absolute() and ".." not in path.parts


def _load_acceptance(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise VerificationError("acceptance manifest must be an object")
    if value.get("schema_version") != 2:
        raise VerificationError("unsupported acceptance manifest schema")
    return value


def _as_string_list(value: Any, *, field: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(f"{field} must be a string list")
        return []
    return list(value)


def _verify_file_hash_manifest(
    root: Path,
    manifest_path: Path,
    *,
    required_paths: Iterable[str],
    errors: list[str],
    label: str,
) -> dict[str, str]:
    try:
        data = _read_json(manifest_path)
    except VerificationError as exc:
        errors.append(str(exc))
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label} hash manifest is not an object")
        return {}
    hashes = data.get("files")
    if not isinstance(hashes, dict):
        errors.append(f"{label} hash manifest missing files object")
        return {}

    normalized: dict[str, str] = {}
    for relative, expected in hashes.items():
        if not isinstance(relative, str) or not _safe_relative(relative):
            errors.append(f"{label} unsafe manifest path: {relative!r}")
            continue
        if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
            errors.append(f"{label} invalid SHA-256 for {relative}")
            continue
        path = root / relative
        if not path.is_file() or path.is_symlink():
            errors.append(f"{label} missing regular file: {relative}")
            continue
        if sha256_file(path) != expected:
            errors.append(f"{label} hash mismatch: {relative}")
        normalized[relative] = expected

    for relative in required_paths:
        if relative not in normalized:
            errors.append(f"{label} required file absent from hash manifest: {relative}")
    return normalized


def _read_required_text(
    root: Path,
    relative: str,
    hashes: Mapping[str, str],
    errors: list[str],
    *,
    label: str,
) -> str:
    if relative not in hashes:
        errors.append(f"{label} is not anchored in the trusted hash manifest: {relative}")
        return ""
    path = root / relative
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        errors.append(f"cannot read {label} {relative}: {exc}")
        return ""


def _load_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = _read_json(path)
    except VerificationError as exc:
        errors.append(str(exc))
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} is not an object")
        return {}
    return value


def _verify_source_anchor(
    source_anchor_root: Path,
    *,
    cases: Mapping[str, Any],
    contract_path: str,
    contract_blob: str,
    errors: list[str],
) -> dict[str, dict[str, str]]:
    anchors: dict[str, dict[str, str]] = {}
    for case_id, rule in cases.items():
        expected_commit = rule.get("input_commit") if isinstance(rule, dict) else None
        repo = source_anchor_root / f"case-{case_id}"
        if not isinstance(expected_commit, str) or not SHA1_RE.fullmatch(expected_commit):
            errors.append(f"CASE-{case_id} trusted input commit is invalid")
            continue
        if not repo.is_dir():
            errors.append(f"CASE-{case_id} independent source anchor checkout missing")
            continue
        try:
            head = _run_git(repo, "rev-parse", "HEAD")
            if head != expected_commit:
                errors.append(f"CASE-{case_id} source anchor HEAD mismatch")
            if _run_git(repo, "status", "--porcelain", "--untracked-files=all"):
                errors.append(f"CASE-{case_id} source anchor checkout is dirty")
            _run_git(repo, "fsck", "--strict")
            tree = _run_git(repo, "rev-parse", f"{expected_commit}^{{tree}}")
            observed_blob = _run_git(repo, "rev-parse", f"{expected_commit}:{contract_path}")
            if observed_blob != contract_blob:
                errors.append(f"CASE-{case_id} independent contract blob mismatch")
            anchors[case_id] = {
                "commit": expected_commit,
                "tree": tree,
                "contract_blob": observed_blob,
            }
        except VerificationError as exc:
            errors.append(str(exc))
    return anchors


def _verify_result_bundle(
    bundle_path: Path,
    *,
    case_id: str,
    case_rule: Mapping[str, Any],
    observation: Mapping[str, Any],
    source_anchor: Mapping[str, str] | None,
    contract_path: str,
    errors: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {"case_id": case_id, "verified": False}
    if not bundle_path.is_file() or bundle_path.is_symlink():
        errors.append(f"CASE-{case_id} result bundle missing")
        return result
    actual_bundle_hash = sha256_file(bundle_path)
    result["bundle_sha256"] = actual_bundle_hash
    if observation.get("bundle_sha256") != actual_bundle_hash:
        errors.append(f"CASE-{case_id} bundle hash mismatch")

    input_commit = case_rule.get("input_commit")
    result_commit = observation.get("result_commit")
    if not isinstance(input_commit, str) or not SHA1_RE.fullmatch(input_commit):
        errors.append(f"CASE-{case_id} invalid trusted input commit")
        return result
    if not isinstance(result_commit, str) or not SHA1_RE.fullmatch(result_commit):
        errors.append(f"CASE-{case_id} invalid observed result commit")
        return result

    with tempfile.TemporaryDirectory(prefix=f"p1-verifier-case-{case_id}-") as temporary:
        repo = Path(temporary) / "repo"
        completed = subprocess.run(
            ["git", "clone", "--quiet", str(bundle_path), str(repo)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**_git_env(Path(temporary) / "empty-home"), "GIT_ALLOW_PROTOCOL": "file"},
        )
        if completed.returncode != 0:
            errors.append(f"CASE-{case_id} bundle clone failed: {completed.stderr.strip()}")
            return result
        try:
            _run_git(repo, "cat-file", "-e", f"{input_commit}^{{commit}}")
            _run_git(repo, "cat-file", "-e", f"{result_commit}^{{commit}}")
            parent = _run_git(repo, "rev-parse", f"{result_commit}^")
            if parent != input_commit:
                errors.append(f"CASE-{case_id} result parent is not the input commit")
            count = _run_git(repo, "rev-list", "--count", f"{input_commit}..{result_commit}")
            if count != "1":
                errors.append(f"CASE-{case_id} does not contain exactly one result commit")
            paths = [line for line in _run_git(
                repo, "diff", "--name-only", "--diff-filter=ACDMRTUXB",
                input_commit, result_commit,
            ).splitlines() if line]
            expected_path = case_rule.get("allowed_path")
            if paths != [expected_path]:
                errors.append(
                    f"CASE-{case_id} changed paths {paths!r}, expected {[expected_path]!r}"
                )
            input_tree = _run_git(repo, "rev-parse", f"{input_commit}^{{tree}}")
            input_contract_blob = _run_git(repo, "rev-parse", f"{input_commit}:{contract_path}")
            if source_anchor is None:
                errors.append(f"CASE-{case_id} independent source anchor missing")
            else:
                if input_tree != source_anchor.get("tree"):
                    errors.append(f"CASE-{case_id} input tree differs from independent source anchor")
                if input_contract_blob != source_anchor.get("contract_blob"):
                    errors.append(f"CASE-{case_id} contract blob differs from independent source anchor")
            result_tree = _run_git(repo, "rev-parse", f"{result_commit}^{{tree}}")
            result.update({
                "input_commit": input_commit,
                "input_tree": input_tree,
                "contract_blob": input_contract_blob,
                "result_commit": result_commit,
                "parent": parent,
                "changed_paths": paths,
                "result_tree": result_tree,
            })
        except VerificationError as exc:
            errors.append(str(exc))
            return result
    result["verified"] = True
    return result


def _normalized_command(inspect: Mapping[str, Any]) -> list[str]:
    config = inspect.get("Config")
    if not isinstance(config, dict):
        return []
    result: list[str] = []
    entrypoint = config.get("Entrypoint")
    command = config.get("Cmd")
    for value in (entrypoint, command):
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, list):
            result.extend(str(item) for item in value)
    return result


def _verify_nested_operation_ledger(
    *,
    execution_dir: Path,
    execution_hashes: Mapping[str, str],
    acceptance: Mapping[str, Any],
    errors: list[str],
) -> dict[str, Any]:
    ledger_path = execution_dir / "nested-operation-ledger.json"
    images_path = execution_dir / "approved-nested-images.json"
    if "nested-operation-ledger.json" not in execution_hashes or not ledger_path.is_file():
        errors.append("trusted nested operation ledger missing")
        return {"verified": False, "containers": 0, "network_enabled": 0}
    if "approved-nested-images.json" not in execution_hashes or not images_path.is_file():
        errors.append("trusted approved nested image manifest missing")
        return {"verified": False, "containers": 0, "network_enabled": 0}

    ledger = _load_object(ledger_path, "trusted nested operation ledger", errors)
    approved = _load_object(images_path, "trusted approved nested image manifest", errors)
    if ledger.get("schema_version") != 1:
        errors.append("trusted nested operation ledger schema mismatch")
    if approved.get("schema_version") != 1:
        errors.append("approved nested image manifest schema mismatch")
    if ledger.get("collector_authority") != "TRUSTED_HOST_HARNESS":
        errors.append("nested operation ledger lacks trusted host authority")
    if approved.get("authority") != "TRUSTED_HOST_HARNESS":
        errors.append("approved nested image manifest lacks trusted host authority")
    if ledger.get("ready_before_candidate") is not True:
        errors.append("nested operation collector was not ready before candidate execution")
    if ledger.get("complete") is not True:
        errors.append("nested operation ledger is incomplete")
    if ledger.get("overflow") is not False:
        errors.append("nested operation ledger overflowed")
    if ledger.get("collector_error") not in (None, ""):
        errors.append("nested operation collector reported an error")
    if ledger.get("approved_images_sha256") != sha256_file(images_path):
        errors.append("nested operation ledger is not bound to approved image identities")

    trusted_refs = acceptance.get("approved_nested_images")
    if not isinstance(trusted_refs, list) or not all(isinstance(item, str) for item in trusted_refs):
        raise VerificationError("approved_nested_images must be a string list")
    image_entries = approved.get("images")
    if not isinstance(image_entries, dict):
        errors.append("approved nested image manifest lacks images object")
        image_entries = {}
    if sorted(image_entries) != sorted(trusted_refs):
        errors.append("approved nested image references differ from trusted acceptance")

    approved_ids: dict[str, str] = {}
    for ref in trusted_refs:
        entry = image_entries.get(ref)
        if not isinstance(entry, dict):
            errors.append(f"approved nested image identity missing: {ref}")
            continue
        image_id = entry.get("id")
        if not isinstance(image_id, str) or not IMAGE_ID_RE.fullmatch(image_id):
            errors.append(f"approved nested image ID invalid: {ref}")
            continue
        repo_digests = entry.get("repo_digests")
        if not isinstance(repo_digests, list) or ref not in repo_digests:
            errors.append(f"approved nested image RepoDigests do not contain pinned ref: {ref}")
        approved_ids[ref] = image_id

    events = ledger.get("events")
    if not isinstance(events, list):
        errors.append("nested operation ledger events must be a list")
        events = []
    max_events = acceptance.get("max_nested_events", 0)
    if not isinstance(max_events, int) or max_events <= 0:
        raise VerificationError("max_nested_events must be a positive integer")
    if len(events) > max_events:
        errors.append("nested operation ledger exceeds trusted event limit")

    by_container: dict[str, list[dict[str, Any]]] = defaultdict(list)
    expected_sequence = 1
    image_event_actions: list[str] = []
    exec_events: list[str] = []
    for raw in events:
        if not isinstance(raw, dict):
            errors.append("nested operation ledger contains a non-object event")
            continue
        if raw.get("sequence") != expected_sequence:
            errors.append("nested operation ledger sequence is not contiguous")
        expected_sequence += 1
        event_type = raw.get("type")
        action = raw.get("action")
        event_id = raw.get("id")
        time_nano = raw.get("time_nano")
        if not isinstance(action, str) or not action:
            errors.append("nested operation ledger event action is invalid")
        if not isinstance(time_nano, int) or time_nano <= 0:
            errors.append("nested operation ledger event time is invalid")
        if event_type == "image":
            image_event_actions.append(str(action))
        elif event_type == "container":
            if not isinstance(event_id, str) or not CONTAINER_ID_RE.fullmatch(event_id):
                errors.append("nested operation ledger container ID is invalid")
                continue
            by_container[event_id].append(raw)
            if str(action).startswith("exec_"):
                exec_events.append(str(action))
        else:
            errors.append(f"nested operation ledger contains unsupported event type: {event_type!r}")

    if image_event_actions:
        errors.append(f"nested image state changed after collector readiness: {image_event_actions}")
    if acceptance.get("forbid_nested_exec") is True and exec_events:
        errors.append(f"nested Docker exec operations are forbidden: {exec_events}")

    max_containers = acceptance.get("max_nested_containers", 0)
    if not isinstance(max_containers, int) or max_containers <= 0:
        raise VerificationError("max_nested_containers must be a positive integer")
    if len(by_container) > max_containers:
        errors.append("nested operation ledger exceeds trusted container limit")

    network_enabled: list[dict[str, Any]] = []
    verified_containers: list[dict[str, Any]] = []
    allowed_sources = acceptance.get("allowed_nested_mount_sources")
    if not isinstance(allowed_sources, list) or not all(isinstance(item, str) for item in allowed_sources):
        raise VerificationError("allowed_nested_mount_sources must be a string list")

    for container_id, container_events in sorted(by_container.items()):
        actions = [str(item.get("action")) for item in container_events]
        for required in ("create", "start", "die", "destroy"):
            if actions.count(required) != 1:
                errors.append(f"nested container {container_id} lifecycle lacks exactly one {required}")
        positions = {name: actions.index(name) for name in ("create", "start", "die", "destroy") if name in actions}
        if len(positions) == 4 and not (
            positions["create"] < positions["start"] < positions["die"] < positions["destroy"]
        ):
            errors.append(f"nested container {container_id} lifecycle order is invalid")

        create_events = [item for item in container_events if item.get("action") == "create"]
        if len(create_events) != 1:
            continue
        create = create_events[0]
        inspect = create.get("inspect")
        if create.get("inspect_error") not in (None, ""):
            errors.append(f"nested container {container_id} create inspect failed")
        if not isinstance(inspect, dict):
            errors.append(f"nested container {container_id} create inspect missing")
            continue
        if inspect.get("Id") != container_id:
            errors.append(f"nested container {container_id} inspect ID mismatch")
        if create.get("inspect_sha256") != _canonical_sha256(inspect):
            errors.append(f"nested container {container_id} inspect hash mismatch")

        config = inspect.get("Config") if isinstance(inspect.get("Config"), dict) else {}
        host = inspect.get("HostConfig") if isinstance(inspect.get("HostConfig"), dict) else {}
        image_ref = config.get("Image")
        image_id = inspect.get("Image")
        if image_ref not in approved_ids:
            errors.append(f"nested container {container_id} used an unapproved image reference: {image_ref!r}")
        elif image_id != approved_ids.get(str(image_ref)):
            errors.append(f"nested container {container_id} image ID differs from trusted pre-pull identity")
        if host.get("Privileged") is not False:
            errors.append(f"nested container {container_id} is privileged")
        cap_add = host.get("CapAdd")
        if cap_add not in (None, []):
            errors.append(f"nested container {container_id} adds capabilities")
        cap_drop = host.get("CapDrop")
        if not isinstance(cap_drop, list) or "ALL" not in {str(item).upper() for item in cap_drop}:
            errors.append(f"nested container {container_id} does not drop all capabilities")
        security_opt = host.get("SecurityOpt")
        if not isinstance(security_opt, list):
            security_opt = []
        lowered_security = [str(item).lower() for item in security_opt]
        if not any("no-new-privileges" in item for item in lowered_security):
            errors.append(f"nested container {container_id} lacks no-new-privileges")
        if any("unconfined" in item for item in lowered_security):
            errors.append(f"nested container {container_id} uses an unconfined security option")
        for field in ("PidMode", "IpcMode", "UTSMode", "CgroupnsMode"):
            if host.get(field) not in (None, "", "private"):
                errors.append(f"nested container {container_id} uses forbidden {field}")
        if host.get("Devices") not in (None, []):
            errors.append(f"nested container {container_id} exposes devices")
        if host.get("DeviceRequests") not in (None, []):
            errors.append(f"nested container {container_id} has device requests")
        if host.get("VolumesFrom") not in (None, []):
            errors.append(f"nested container {container_id} uses volumes-from")

        mounts = inspect.get("Mounts")
        if not isinstance(mounts, list):
            errors.append(f"nested container {container_id} mounts are missing")
            mounts = []
        for mount in mounts:
            if not isinstance(mount, dict):
                errors.append(f"nested container {container_id} mount is not an object")
                continue
            source = mount.get("Source")
            destination = mount.get("Destination")
            if not isinstance(source, str) or not any(
                source == prefix or source.startswith(prefix.rstrip("/") + "/")
                for prefix in allowed_sources
            ):
                errors.append(f"nested container {container_id} mount source is outside isolated roots: {source!r}")
            if not isinstance(destination, str) or not destination.startswith("/"):
                errors.append(f"nested container {container_id} mount destination is invalid")

        network_mode = host.get("NetworkMode")
        command = _normalized_command(inspect)
        record = {
            "id": container_id,
            "image_ref": image_ref,
            "image_id": image_id,
            "network_mode": network_mode,
            "command": command,
        }
        verified_containers.append(record)
        if network_mode != "none":
            network_enabled.append(record)

    required_network = acceptance.get("required_network_enabled_containers")
    if not isinstance(required_network, int) or required_network < 0:
        raise VerificationError("required_network_enabled_containers must be a non-negative integer")
    if len(network_enabled) != required_network:
        errors.append(
            f"nested operation ledger has {len(network_enabled)} network-enabled containers, expected {required_network}"
        )
    canonical_url = str(acceptance.get("canonical_source_url", ""))
    acquisition_image = acceptance.get("network_acquisition_image")
    expected_commits = sorted(
        str(rule.get("input_commit"))
        for rule in acceptance.get("cases", {}).values()
        if isinstance(rule, dict)
    )
    observed_commits: list[str] = []
    for acquisition in network_enabled:
        if acquisition.get("network_mode") != "bridge":
            errors.append("network-enabled acquisition container does not use bridge mode")
        if acquisition.get("image_ref") != acquisition_image:
            errors.append("network-enabled acquisition container does not use the trusted Git image")
        command = [str(item) for item in acquisition.get("command", [])]
        if command[:2] != ["/bin/busybox", "env"] and "/bin/busybox" not in command:
            errors.append("network-enabled acquisition container lacks the trusted busybox entrypoint")
        if "-i" not in command or "/usr/bin/git" not in command or "fetch" not in command:
            errors.append("network-enabled acquisition container command is not the controlled Git fetch")
        if command.count(canonical_url) != 1:
            errors.append("network-enabled acquisition container does not bind exactly one canonical endpoint")
        urls = [item for item in command if URL_RE.match(item)]
        if urls != [canonical_url]:
            errors.append(f"network-enabled acquisition command contains unexpected URLs: {urls}")
        commit_args = [item for item in command if SHA1_RE.fullmatch(item)]
        if len(commit_args) != 1:
            errors.append("network-enabled acquisition command does not bind exactly one full commit")
        else:
            observed_commits.append(commit_args[0])
    if sorted(observed_commits) != expected_commits:
        errors.append(
            f"network-enabled acquisitions do not map one-to-one to trusted CASE commits: {observed_commits}"
        )

    return {
        "verified": not any("nested" in error.lower() for error in errors),
        "events": len(events),
        "containers": len(by_container),
        "network_enabled": len(network_enabled),
        "verified_containers": verified_containers,
    }


def verify(
    *,
    acceptance_path: Path,
    controller_dir: Path,
    execution_dir: Path,
    candidate_dir: Path,
    source_anchor_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    acceptance = _load_acceptance(acceptance_path)
    errors: list[str] = []
    warnings: list[str] = []

    required_controller = acceptance.get("required_controller_files", [])
    required_execution = acceptance.get("required_execution_files", [])
    if not isinstance(required_controller, list) or not all(isinstance(x, str) for x in required_controller):
        raise VerificationError("required_controller_files must be a string list")
    if not isinstance(required_execution, list) or not all(isinstance(x, str) for x in required_execution):
        raise VerificationError("required_execution_files must be a string list")

    controller_hashes = _verify_file_hash_manifest(
        controller_dir, controller_dir / "files-sha256.json",
        required_paths=required_controller, errors=errors, label="controller",
    )
    execution_hashes = _verify_file_hash_manifest(
        execution_dir, execution_dir / "files-sha256.json",
        required_paths=required_execution, errors=errors, label="execution",
    )

    controller = _load_object(controller_dir / "controller-manifest.json", "controller manifest", errors)
    scope = _load_object(controller_dir / "scope-report.json", "scope report", errors)
    identities = _load_object(controller_dir / "workflow-identities.json", "workflow identities", errors)
    observation = _load_object(execution_dir / "observation-manifest.json", "execution observation", errors)
    network_observation = _load_object(execution_dir / "network-observation.json", "network observation", errors)
    cleanup_state = _load_object(execution_dir / "cleanup-state.json", "cleanup state", errors)

    candidate_sha = controller.get("candidate_sha")
    if not isinstance(candidate_sha, str) or not SHA1_RE.fullmatch(candidate_sha):
        errors.append("controller candidate_sha is invalid")
        candidate_sha = ""
    if controller.get("event_name") != "workflow_dispatch":
        errors.append("controller event is not workflow_dispatch")
    if controller.get("target_ref") != acceptance.get("authorized_target_ref"):
        errors.append("controller target_ref is not authorized")
    if controller.get("expected_sha") != candidate_sha:
        errors.append("controller expected_sha does not equal candidate_sha")
    if controller.get("parent_sha") != acceptance.get("required_parent_sha"):
        errors.append("candidate parent does not match the trusted ADR")
    if controller.get("candidate_tests_authority") != "OBSERVATIONAL":
        errors.append("candidate tests were not classified as observational")
    if controller.get("execution_mode") != "verify-candidate":
        errors.append("non-production execution mode cannot produce authoritative PASS")

    if scope.get("changed_paths") != acceptance.get("allowed_changed_paths"):
        errors.append("controller scope report does not match the exact allowlist")
    if scope.get("status") != "PASS":
        errors.append("controller scope report is not PASS")

    bundle_path = controller_dir / "candidate-source.bundle"
    if bundle_path.is_file():
        if controller.get("candidate_bundle_sha256") != sha256_file(bundle_path):
            errors.append("controller candidate bundle hash mismatch")
    else:
        errors.append("controller candidate bundle missing")

    for key in ("controller_workflow", "candidate_workflow", "trusted_verifier", "acceptance_manifest"):
        identity = identities.get(key)
        if not isinstance(identity, dict):
            errors.append(f"missing workflow identity: {key}")
            continue
        if not SHA256_RE.fullmatch(str(identity.get("sha256", ""))):
            errors.append(f"invalid workflow identity SHA-256: {key}")
        relative = identity.get("artifact_path")
        if not isinstance(relative, str) or relative not in controller_hashes:
            errors.append(f"workflow identity not anchored in controller artifact: {key}")

    if candidate_dir.is_dir():
        try:
            if _run_git(candidate_dir, "rev-parse", "HEAD") != candidate_sha:
                errors.append("fresh verifier checkout SHA differs from controller SHA")
            if _run_git(candidate_dir, "rev-parse", "HEAD^") != acceptance.get("required_parent_sha"):
                errors.append("fresh verifier checkout parent differs from trusted ADR")
            if _run_git(candidate_dir, "status", "--porcelain", "--untracked-files=all"):
                errors.append("fresh verifier checkout is not clean")
            _run_git(candidate_dir, "fsck", "--strict")
        except VerificationError as exc:
            errors.append(str(exc))
    else:
        errors.append("fresh candidate checkout is missing")

    cases_rule = acceptance.get("cases")
    if not isinstance(cases_rule, dict):
        raise VerificationError("acceptance cases must be an object")
    contract_path = str(acceptance.get("contract_path", "PILOT_CONTRACT.md"))
    contract_blob = str(acceptance.get("required_contract_blob", ""))
    if not SHA1_RE.fullmatch(contract_blob):
        raise VerificationError("required_contract_blob must be a full SHA-1")
    source_anchors = _verify_source_anchor(
        source_anchor_root, cases=cases_rule, contract_path=contract_path,
        contract_blob=contract_blob, errors=errors,
    )

    if observation.get("candidate_sha") != candidate_sha:
        errors.append("execution observation candidate SHA mismatch")
    if observation.get("execution_mode") != controller.get("execution_mode"):
        errors.append("execution mode differs from controller manifest")
    if observation.get("observation_authority") != "TRUSTED_HOST_HARNESS":
        errors.append("execution observation was not produced by the trusted harness")
    if observation.get("candidate_process_domain") != "UNTRUSTED_NESTED_CONTAINER":
        errors.append("candidate was not confined to the declared untrusted process domain")
    if observation.get("nested_daemon_rootless") is not True:
        errors.append("nested Docker daemon was not observed as rootless")
    for field, message in (
        ("host_docker_socket_mounted", "candidate had access to the host Docker socket"),
        ("controller_evidence_visible", "candidate could see controller evidence"),
        ("verifier_bundle_visible", "candidate could see the trusted verifier bundle"),
        ("github_token_visible", "candidate could see a GitHub token"),
        ("secrets_visible", "candidate could see secrets"),
        ("candidate_direct_egress", "candidate process had direct external network egress"),
    ):
        if observation.get(field) is not False:
            errors.append(message)
    if observation.get("nested_daemon_egress") is not True:
        errors.append("isolated nested daemon egress was not established")
    if observation.get("cleanup_confirmed") is not True or cleanup_state.get("cleanup_confirmed") is not True:
        errors.append("execution cleanup was not confirmed")
    if observation.get("candidate_tests_authority") != "OBSERVATIONAL":
        errors.append("execution treated candidate tests as authoritative")
    for field, label in (
        ("trusted_probes_exit_code", "trusted black-box probe"),
        ("candidate_tests_exit_code", "candidate test observation"),
        ("sandbox_exit_code", "trusted sandbox observation"),
        ("acquisition_exit_code", "controlled acquisition observation"),
    ):
        if observation.get(field) != 0:
            errors.append(f"{label} did not exit zero")

    if network_observation.get("candidate_network") != "internal-only":
        errors.append("trusted network observation does not prove internal-only candidate network")
    if network_observation.get("nested_daemon_egress") is not True:
        errors.append("trusted network observation does not prove nested-daemon egress")
    if network_observation.get("host_docker_socket_mounted") is not False:
        errors.append("trusted network observation reports host Docker socket exposure")

    forbidden_env = set(acceptance.get("forbidden_candidate_environment", []))
    observed_env = set(_as_string_list(
        observation.get("candidate_environment_names", []),
        field="candidate_environment_names", errors=errors,
    ))
    leaked_env = sorted(forbidden_env & observed_env)
    if leaked_env:
        errors.append(f"candidate environment exposed forbidden names: {leaked_env}")

    mounts = observation.get("candidate_mounts")
    if not isinstance(mounts, list):
        errors.append("candidate_mounts must be a list")
        mounts = []
    for mount in mounts:
        if not isinstance(mount, dict):
            errors.append("candidate mount entry is not an object")
            continue
        joined = f"{mount.get('source', '')}\n{mount.get('destination', '')}"
        for fragment in acceptance.get("forbidden_candidate_mount_fragments", []):
            if fragment in joined:
                errors.append(f"candidate mount crossed forbidden boundary: {fragment}")

    for relative, label in (
        ("process-tree.txt", "trusted process-tree observation"),
        ("network-observation.json", "trusted network observation"),
        ("cleanup-state.json", "trusted cleanup observation"),
        ("nested-docker-security.json", "nested Docker security observation"),
    ):
        path = execution_dir / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"{label} missing")
    nested_security = _read_required_text(
        execution_dir, "nested-docker-security.json", execution_hashes, errors,
        label="nested Docker security observation",
    )
    if "rootless" not in nested_security.lower():
        errors.append("nested Docker security observation lacks rootless marker")

    ledger_summary = _verify_nested_operation_ledger(
        execution_dir=execution_dir,
        execution_hashes=execution_hashes,
        acceptance=acceptance,
        errors=errors,
    )

    trusted_probe_log = _read_required_text(
        execution_dir, "logs/trusted-probes.log", execution_hashes, errors,
        label="trusted black-box probe log",
    )
    if "TRUSTED_BLACK_BOX_PROBES: PASS" not in trusted_probe_log:
        errors.append("trusted black-box probes did not confirm fail-closed inputs")
    sandbox_log = _read_required_text(
        execution_dir, "logs/sandbox.log", execution_hashes, errors,
        label="sandbox black-box log",
    )
    if "skipped" in sandbox_log.lower() or "FAILED" in sandbox_log or "ERROR" in sandbox_log:
        errors.append("sandbox black-box run was skipped or failed")
    if "Ran 10 tests" not in sandbox_log or "OK" not in sandbox_log:
        errors.append("sandbox black-box run lacks the expected successful test result")

    source_acquisition = _load_object(
        execution_dir / "results/source_acquisition.json", "source acquisition observation", errors,
    )
    if source_acquisition.get("input_model") != "CONTROLLED_HTTPS_FETCH_V1":
        errors.append("source acquisition observation has the wrong input model")
    request_observation = source_acquisition.get("request", {})
    origin_observation = source_acquisition.get("origin_anchor", {})
    if not isinstance(request_observation, dict):
        request_observation = {}
    if not isinstance(origin_observation, dict):
        origin_observation = {}
    if request_observation.get("repository") != acceptance.get("source_repository"):
        errors.append("source acquisition observation has the wrong repository")
    if origin_observation.get("canonical_url") != acceptance.get("canonical_source_url"):
        errors.append("source acquisition observation has the wrong canonical URL")
    if origin_observation.get("local_checkout_used") is not False:
        errors.append("source acquisition observation does not reject the local checkout")
    if origin_observation.get("user_supplied_url_used") is not False:
        errors.append("source acquisition observation accepted a user-supplied URL")
    if source_acquisition.get("outcome") != "ACQUIRED_REVIEW_REQUIRED":
        errors.append("source acquisition observation lacks the required review outcome")

    case_observations = observation.get("cases")
    if not isinstance(case_observations, dict):
        errors.append("execution cases must be an object")
        case_observations = {}
    verified_cases: dict[str, Any] = {}
    for case_id, case_rule in cases_rule.items():
        case_observation = case_observations.get(case_id)
        if not isinstance(case_observation, dict):
            errors.append(f"CASE-{case_id} observation missing")
            continue
        if case_observation.get("exit_code") != 0:
            errors.append(f"CASE-{case_id} candidate process did not exit zero")
        if case_observation.get("skipped") is not False:
            errors.append(f"CASE-{case_id} was skipped or skip state is untrusted")
        if case_observation.get("harness_status") != "OBSERVED_COMPLETED":
            errors.append(f"CASE-{case_id} lacks trusted harness completion")
        if case_observation.get("candidate_status") != case_rule.get("required_status"):
            errors.append(f"CASE-{case_id} candidate observation lacks the required review status")
        for field_name, relative in (
            ("log", case_observation.get("log_path")),
            ("trace", case_observation.get("trace_path")),
        ):
            if not isinstance(relative, str) or relative not in execution_hashes:
                errors.append(f"CASE-{case_id} {field_name} is not in the trusted hash manifest")
        bundle_rel = case_observation.get("bundle_path")
        if not isinstance(bundle_rel, str) or not _safe_relative(bundle_rel):
            errors.append(f"CASE-{case_id} invalid result bundle path")
            continue
        verified_cases[case_id] = _verify_result_bundle(
            execution_dir / bundle_rel,
            case_id=case_id,
            case_rule=case_rule,
            observation=case_observation,
            source_anchor=source_anchors.get(case_id),
            contract_path=contract_path,
            errors=errors,
        )

    candidate_declared_result = observation.get("candidate_declared_result", "ABSENT")
    if candidate_declared_result not in ("ABSENT", "PASS", "FAIL", "SUCCESS", "UNKNOWN"):
        warnings.append("candidate declared result had an unrecognized value")
    if observation.get("candidate_boundary_markers"):
        errors.append("candidate attempted to influence a forbidden authority boundary")
    for path in execution_dir.rglob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and value.get("status") == "PASS":
            errors.append(f"candidate terminal PASS observed and ignored: {path.relative_to(execution_dir)}")

    verifier_sha = sha256_file(Path(__file__))
    acceptance_sha = sha256_file(acceptance_path)
    report = {
        "schema_version": 2,
        "authoritative_result": "PASS" if not errors else "FAIL",
        "candidate_declared_result": candidate_declared_result,
        "candidate_declared_result_authority": "IGNORED_FOR_AUTHORITY",
        "candidate_sha": candidate_sha or None,
        "workflow_sha": controller.get("workflow_sha"),
        "controller_manifest_sha256": (
            sha256_file(controller_dir / "controller-manifest.json")
            if (controller_dir / "controller-manifest.json").is_file() else None
        ),
        "execution_observation_sha256": (
            sha256_file(execution_dir / "observation-manifest.json")
            if (execution_dir / "observation-manifest.json").is_file() else None
        ),
        "nested_operation_ledger_sha256": (
            sha256_file(execution_dir / "nested-operation-ledger.json")
            if (execution_dir / "nested-operation-ledger.json").is_file() else None
        ),
        "trusted_verifier_sha256": verifier_sha,
        "acceptance_manifest_sha256": acceptance_sha,
        "source_anchors": source_anchors,
        "nested_operation_summary": ledger_summary,
        "verified_cases": verified_cases,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "authoritative-final-gate.json", report)
    _write_json(output_dir / "authoritative-files-sha256.json", {
        "schema_version": 1,
        "files": {
            "authoritative-final-gate.json": sha256_file(
                output_dir / "authoritative-final-gate.json"
            )
        },
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acceptance-manifest", type=Path, required=True)
    parser.add_argument("--controller-dir", type=Path, required=True)
    parser.add_argument("--execution-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--source-anchor-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = verify(
            acceptance_path=args.acceptance_manifest.resolve(),
            controller_dir=args.controller_dir.resolve(),
            execution_dir=args.execution_dir.resolve(),
            candidate_dir=args.candidate_dir.resolve(),
            source_anchor_root=args.source_anchor_root.resolve(),
            output_dir=args.output_dir.resolve(),
        )
    except VerificationError as exc:
        print(f"VERIFIER_CONFIGURATION_ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["authoritative_result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
