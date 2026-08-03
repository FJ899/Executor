#!/usr/bin/env python3
"""Trusted authoritative verifier for Executor P1 exact-ref observations.

The verifier is stdlib-only and must be loaded from the trusted workflow/main
commit. It never imports candidate modules and never accepts candidate-owned
tests, reports, or PASS declarations as authority.
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
from pathlib import Path
from typing import Any, Iterable, Mapping

SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class VerificationError(RuntimeError):
    """Invalid trusted verifier invocation or malformed trusted configuration."""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise VerificationError(f"missing JSON file: {path}") from None
    except json.JSONDecodeError as exc:
        raise VerificationError(f"invalid JSON in {path}: {exc}") from None


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


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
    if value.get("schema_version") != 1:
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
            status = _run_git(repo, "status", "--porcelain", "--untracked-files=all")
            if status:
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
            paths = [
                line
                for line in _run_git(
                    repo,
                    "diff",
                    "--name-only",
                    "--diff-filter=ACDMRTUXB",
                    input_commit,
                    result_commit,
                ).splitlines()
                if line
            ]
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
            result.update(
                {
                    "input_commit": input_commit,
                    "input_tree": input_tree,
                    "contract_blob": input_contract_blob,
                    "result_commit": result_commit,
                    "parent": parent,
                    "changed_paths": paths,
                    "result_tree": result_tree,
                }
            )
        except VerificationError as exc:
            errors.append(str(exc))
            return result
    result["verified"] = True
    return result


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
        controller_dir,
        controller_dir / "files-sha256.json",
        required_paths=required_controller,
        errors=errors,
        label="controller",
    )
    execution_hashes = _verify_file_hash_manifest(
        execution_dir,
        execution_dir / "files-sha256.json",
        required_paths=required_execution,
        errors=errors,
        label="execution",
    )

    def load_object(path: Path, label: str) -> dict[str, Any]:
        try:
            value = _read_json(path)
        except VerificationError as exc:
            errors.append(str(exc))
            return {}
        if not isinstance(value, dict):
            errors.append(f"{label} is not an object")
            return {}
        return value

    controller = load_object(controller_dir / "controller-manifest.json", "controller manifest")
    scope = load_object(controller_dir / "scope-report.json", "scope report")
    identities = load_object(controller_dir / "workflow-identities.json", "workflow identities")
    observation = load_object(execution_dir / "observation-manifest.json", "execution observation")
    network_observation = load_object(execution_dir / "network-observation.json", "network observation")
    cleanup_state = load_object(execution_dir / "cleanup-state.json", "cleanup state")

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

    for key in (
        "controller_workflow",
        "candidate_workflow",
        "trusted_verifier",
        "acceptance_manifest",
    ):
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
        source_anchor_root,
        cases=cases_rule,
        contract_path=contract_path,
        contract_blob=contract_blob,
        errors=errors,
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
    if observation.get("host_docker_socket_mounted") is not False:
        errors.append("candidate had access to the host Docker socket")
    if observation.get("controller_evidence_visible") is not False:
        errors.append("candidate could see controller evidence")
    if observation.get("verifier_bundle_visible") is not False:
        errors.append("candidate could see the trusted verifier bundle")
    if observation.get("github_token_visible") is not False:
        errors.append("candidate could see a GitHub token")
    if observation.get("secrets_visible") is not False:
        errors.append("candidate could see secrets")
    if observation.get("candidate_direct_egress") is not False:
        errors.append("candidate process had direct external network egress")
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
    observed_env = set(
        _as_string_list(
            observation.get("candidate_environment_names", []),
            field="candidate_environment_names",
            errors=errors,
        )
    )
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
        execution_dir,
        "nested-docker-security.json",
        execution_hashes,
        errors,
        label="nested Docker security observation",
    )
    if "rootless" not in nested_security.lower():
        errors.append("nested Docker security observation lacks rootless marker")

    trusted_probe_log = _read_required_text(
        execution_dir,
        "logs/trusted-probes.log",
        execution_hashes,
        errors,
        label="trusted black-box probe log",
    )
    if "TRUSTED_BLACK_BOX_PROBES: PASS" not in trusted_probe_log:
        errors.append("trusted black-box probes did not confirm fail-closed inputs")

    sandbox_log = _read_required_text(
        execution_dir,
        "logs/sandbox.log",
        execution_hashes,
        errors,
        label="sandbox black-box log",
    )
    if "skipped" in sandbox_log.lower() or "FAILED" in sandbox_log or "ERROR" in sandbox_log:
        errors.append("sandbox black-box run was skipped or failed")
    if "Ran 10 tests" not in sandbox_log or "OK" not in sandbox_log:
        errors.append("sandbox black-box run lacks the expected successful test result")
    sandbox_trace = _read_required_text(
        execution_dir,
        "traces/sandbox.execve",
        execution_hashes,
        errors,
        label="sandbox exec trace",
    )
    if "--network" not in sandbox_trace or "none" not in sandbox_trace:
        errors.append("sandbox exec trace does not show network-disabled containers")

    acquisition_trace = _read_required_text(
        execution_dir,
        "traces/acquisition.execve",
        execution_hashes,
        errors,
        label="acquisition exec trace",
    )
    canonical_url = str(acceptance.get("canonical_source_url", ""))
    if canonical_url not in acquisition_trace:
        errors.append("acquisition trace lacks the canonical HTTPS source endpoint")
    if "--network" not in acquisition_trace or "bridge" not in acquisition_trace:
        errors.append("acquisition trace lacks the single network-enabled fetch path")
    if "--network" not in acquisition_trace or "none" not in acquisition_trace:
        errors.append("acquisition trace lacks post-fetch network-disabled Git operations")
    for forbidden in ("file://", "ext::", "git://", "ssh://", "GIT_SSH_COMMAND"):
        if forbidden in acquisition_trace:
            errors.append(f"acquisition trace contains forbidden transport/helper: {forbidden}")

    source_acquisition = load_object(
        execution_dir / "results/source_acquisition.json",
        "source acquisition observation",
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
    if origin_observation.get("canonical_url") != canonical_url:
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
        log_rel = case_observation.get("log_path")
        trace_rel = case_observation.get("trace_path")
        for field_name, relative in (("log", log_rel), ("trace", trace_rel)):
            if not isinstance(relative, str) or relative not in execution_hashes:
                errors.append(f"CASE-{case_id} {field_name} is not in the trusted hash manifest")
        if isinstance(trace_rel, str):
            trace = _read_required_text(
                execution_dir,
                trace_rel,
                execution_hashes,
                errors,
                label=f"CASE-{case_id} exec trace",
            )
            if "--network" not in trace or "none" not in trace:
                errors.append(f"CASE-{case_id} trace does not show a network-disabled worker/sandbox")
            if "/var/run/docker.sock" in trace:
                errors.append(f"CASE-{case_id} trace references the host Docker socket")
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
            errors.append(
                f"candidate terminal PASS observed and ignored: {path.relative_to(execution_dir)}"
            )

    verifier_sha = sha256_file(Path(__file__))
    acceptance_sha = sha256_file(acceptance_path)
    controller_manifest_sha = (
        sha256_file(controller_dir / "controller-manifest.json")
        if (controller_dir / "controller-manifest.json").is_file()
        else None
    )
    execution_manifest_sha = (
        sha256_file(execution_dir / "observation-manifest.json")
        if (execution_dir / "observation-manifest.json").is_file()
        else None
    )
    report = {
        "schema_version": 1,
        "authoritative_result": "PASS" if not errors else "FAIL",
        "candidate_declared_result": candidate_declared_result,
        "candidate_declared_result_authority": "IGNORED_FOR_AUTHORITY",
        "candidate_sha": candidate_sha or None,
        "workflow_sha": controller.get("workflow_sha"),
        "controller_manifest_sha256": controller_manifest_sha,
        "execution_observation_sha256": execution_manifest_sha,
        "trusted_verifier_sha256": verifier_sha,
        "acceptance_manifest_sha256": acceptance_sha,
        "source_anchors": source_anchors,
        "verified_cases": verified_cases,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "authoritative-final-gate.json", report)
    _write_json(
        output_dir / "authoritative-files-sha256.json",
        {
            "schema_version": 1,
            "files": {
                "authoritative-final-gate.json": sha256_file(
                    output_dir / "authoritative-final-gate.json"
                )
            },
        },
    )
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
