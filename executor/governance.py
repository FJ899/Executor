from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any

from executor.contracts import ValidationIssue, ValidationResult, ValidationStatus, validate_project_contract, validate_task_contract
from executor.repository_access import RepositoryPathError, canonical_repository_path, read_repository_bytes, read_repository_text, validate_repository_candidate
from executor.repository_identity import repository_identity_from_remote
from executor.strict_json import StrictJsonError, loads_json_object


_COMMIT = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


def _safe_path(value: str) -> bool:
    try:
        canonical_repository_path(value)
    except RepositoryPathError:
        return False
    return True


def _read_regular_bytes(base_dir: str | Path, relative: str) -> bytes:
    _, candidate = validate_repository_candidate(base_dir, relative)
    if not candidate.exists():
        raise FileNotFoundError(relative)
    _, payload = read_repository_bytes(base_dir, relative)
    return payload


def _read_regular_text(base_dir: str | Path, relative: str) -> str:
    _, candidate = validate_repository_candidate(base_dir, relative)
    if not candidate.exists():
        raise FileNotFoundError(relative)
    _, text = read_repository_text(base_dir, relative)
    return text


def _repository_name_from_remote(remote: str) -> str | None:
    identity = repository_identity_from_remote(remote)
    if identity is None or identity[0] != "github.com":
        return None
    return identity[1]


def _git(root: str | Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def _verify_repository_lock(name: str, commit: str, root_value: str | Path) -> ValidationIssue | None:
    root_input = Path(root_value)
    if root_input.is_symlink():
        return ValidationIssue("UNSAFE_REPOSITORY_ROOT", f"Repository root for {name} cannot be a symlink", "$.repositories")
    try:
        root = root_input.resolve(strict=True)
    except OSError as exc:
        return ValidationIssue("REPOSITORY_ROOT_UNAVAILABLE", f"Cannot resolve repository root for {name}: {exc}", "$.repositories")
    if not root.is_dir():
        return ValidationIssue("REPOSITORY_ROOT_UNAVAILABLE", f"Repository root for {name} is not a directory", "$.repositories")
    try:
        remote_result = _git(root, "remote", "get-url", "origin")
        commit_result = _git(root, "cat-file", "-e", f"{commit}^{{commit}}")
    except (OSError, subprocess.SubprocessError) as exc:
        return ValidationIssue("REPOSITORY_VERIFICATION_FAILED", f"Cannot verify repository {name}: {exc}", "$.repositories")
    actual_name = _repository_name_from_remote(remote_result.stdout) if remote_result.returncode == 0 else None
    if actual_name is None or actual_name.lower() != name.lower():
        return ValidationIssue("REPOSITORY_ROOT_MISMATCH", f"Repository root does not resolve to github.com/{name}", "$.repositories")
    if commit_result.returncode != 0:
        return ValidationIssue("REPOSITORY_COMMIT_NOT_FOUND", f"Locked commit is not present in verified repository {name}: {commit}", "$.repositories")
    return None


def _policy_issues(policy: dict[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if policy.get("schema_version") != "executor-policy/1.0":
        issues.append(ValidationIssue("INVALID_POLICY_SCHEMA", "schema_version must be executor-policy/1.0", "$.schema_version"))
    execution = policy.get("execution")
    if not isinstance(execution, dict):
        issues.append(ValidationIssue("MISSING_POLICY_EXECUTION", "execution policy is required", "$.execution"))
    else:
        for key in ("external_projects", "auto_merge", "default_network"):
            if not isinstance(execution.get(key), bool):
                issues.append(ValidationIssue("INVALID_POLICY_EXECUTION", f"execution.{key} must be boolean", f"$.execution.{key}"))
        if not isinstance(execution.get("default_secrets"), list):
            issues.append(ValidationIssue("INVALID_POLICY_EXECUTION", "execution.default_secrets must be a list", "$.execution.default_secrets"))
    hierarchy = policy.get("trust_hierarchy")
    required_prefix = ["executor_policy", "project_contract", "task_contract"]
    if not isinstance(hierarchy, list) or hierarchy[:3] != required_prefix:
        issues.append(ValidationIssue("INVALID_TRUST_HIERARCHY", "executor_policy, project_contract and task_contract must be the first trust levels", "$.trust_hierarchy"))
    if not isinstance(policy.get("hard_veto_evidence_types"), list) or not policy["hard_veto_evidence_types"]:
        issues.append(ValidationIssue("MISSING_HARD_VETO_EVIDENCE", "hard_veto_evidence_types must be non-empty", "$.hard_veto_evidence_types"))
    allowed = policy.get("allowed_objection_types")
    required = {"PASS", "CONCERN", "EVIDENCE_GAP", "POLICY_VETO", "HARD_VETO"}
    if not isinstance(allowed, list) or set(allowed) != required:
        issues.append(ValidationIssue("INVALID_OBJECTION_TYPES", "allowed_objection_types must contain the complete closed set", "$.allowed_objection_types"))
    return issues


def validate_project_bundle(
    contract: dict[str, Any],
    *,
    executor_policy: dict[str, Any] | None,
    base_dir: str | Path | None,
) -> ValidationResult:
    structural = validate_project_contract(contract)
    issues = list(structural.issues)
    gaps: list[ValidationIssue] = []
    if executor_policy is None:
        issues.append(ValidationIssue("EXECUTOR_POLICY_REQUIRED", "The executor policy is required for authoritative project validation", "$.executor_policy"))
    else:
        issues.extend(_policy_issues(executor_policy))

    sources = contract.get("authoritative_sources") if isinstance(contract.get("authoritative_sources"), list) else []
    policy_sources = [item for item in sources if isinstance(item, dict) and item.get("path") == "EXECUTOR_POLICY.yaml" and item.get("role") == "authoritative_instruction"]
    if not policy_sources:
        issues.append(ValidationIssue("POLICY_NOT_AUTHORITATIVE", "EXECUTOR_POLICY.yaml must be an authoritative_instruction", "$.authoritative_sources"))

    if executor_policy is not None:
        execution = executor_policy.get("execution", {}) if isinstance(executor_policy.get("execution"), dict) else {}
        caps = contract.get("capabilities", {}) if isinstance(contract.get("capabilities"), dict) else {}
        project_network = caps.get("network", {}).get("default") if isinstance(caps.get("network"), dict) else None
        if execution.get("default_network") is False and project_network is not False:
            issues.append(ValidationIssue("POLICY_PRECEDENCE_VIOLATION", "Project contract cannot enable network denied by executor policy", "$.capabilities.network.default"))
        policy_secrets = set(execution.get("default_secrets", [])) if isinstance(execution.get("default_secrets"), list) else set()
        project_secrets = set(caps.get("secrets", {}).get("default", [])) if isinstance(caps.get("secrets"), dict) and isinstance(caps.get("secrets", {}).get("default"), list) else set()
        if not project_secrets.issubset(policy_secrets):
            issues.append(ValidationIssue("POLICY_PRECEDENCE_VIOLATION", "Project contract requests secrets denied by executor policy", "$.capabilities.secrets.default"))

    if base_dir is None:
        gaps.append(ValidationIssue("PROJECT_BASE_DIR_REQUIRED", "base_dir is required to verify project sources", "$.authoritative_sources"))
    else:
        paths = [str(contract.get("project", {}).get("entrypoint", ""))] if isinstance(contract.get("project"), dict) else []
        paths.extend(str(item.get("path", "")) for item in sources if isinstance(item, dict))
        for relative in paths:
            if not _safe_path(relative):
                issues.append(ValidationIssue("UNSAFE_PROJECT_SOURCE", f"Unsafe project source path: {relative}", "$.authoritative_sources"))
                continue
            try:
                payload = _read_regular_bytes(base_dir, relative)
            except FileNotFoundError:
                gaps.append(ValidationIssue("PROJECT_SOURCE_NOT_FOUND", f"Required project source not found: {relative}", "$.authoritative_sources"))
                continue
            except OSError as exc:
                gaps.append(ValidationIssue("PROJECT_SOURCE_UNREADABLE", f"Cannot read required project source {relative}: {exc}", "$.authoritative_sources"))
                continue
            except (ValueError, RepositoryPathError) as exc:
                issues.append(ValidationIssue("UNSAFE_PROJECT_SOURCE", f"{relative}: {exc}", "$.authoritative_sources"))
                continue
            if not payload:
                gaps.append(ValidationIssue("PROJECT_SOURCE_EMPTY", f"Required project source is empty: {relative}", "$.authoritative_sources"))
        if executor_policy is not None:
            try:
                policy_text = _read_regular_text(base_dir, "EXECUTOR_POLICY.yaml")
                file_policy = loads_json_object(policy_text)
            except (OSError, ValueError, RepositoryPathError, StrictJsonError) as exc:
                gaps.append(ValidationIssue("POLICY_FILE_UNVERIFIED", f"Cannot verify EXECUTOR_POLICY.yaml: {exc}", "$.executor_policy"))
            else:
                if file_policy != executor_policy:
                    issues.append(ValidationIssue("POLICY_FILE_MISMATCH", "Provided executor policy differs from authoritative EXECUTOR_POLICY.yaml", "$.executor_policy"))

    if issues:
        return ValidationResult(ValidationStatus.INVALID, issues + gaps, contract, authoritative=True)
    if gaps:
        return ValidationResult(ValidationStatus.INSUFFICIENT_EVIDENCE, gaps, contract, authoritative=True)
    return ValidationResult(ValidationStatus.VALID, normalized=contract, authoritative=True)


def validate_task_bundle(
    contract: dict[str, Any],
    *,
    executor_policy: dict[str, Any] | None,
    base_dir: str | Path | None,
    repository_roots: dict[str, str | Path] | None = None,
) -> ValidationResult:
    structural = validate_task_contract(contract)
    issues = list(structural.issues)
    gaps: list[ValidationIssue] = []
    if executor_policy is None:
        issues.append(ValidationIssue("EXECUTOR_POLICY_REQUIRED", "The executor policy is required for authoritative task validation", "$.executor_policy"))
    else:
        issues.extend(_policy_issues(executor_policy))

    roots = repository_roots or {}
    repositories = contract.get("repositories")
    if isinstance(repositories, dict):
        for key, repository in repositories.items():
            path = f"$.repositories.{key}"
            if not isinstance(repository, dict) or not str(repository.get("name", "")).strip():
                issues.append(ValidationIssue("INVALID_REPOSITORY_LOCK", "Repository name is required", path))
                continue
            name = str(repository["name"])
            commit = str(repository.get("commit", ""))
            if not _COMMIT.fullmatch(commit) or set(commit) == {"0"}:
                issues.append(ValidationIssue("UNLOCKED_REPOSITORY", f"Repository {key} requires a concrete 40- or 64-hex commit", f"{path}.commit"))
                continue
            root = roots.get(name)
            if root is None:
                gaps.append(ValidationIssue("REPOSITORY_COMMIT_UNVERIFIED", f"A verified local repository root is required to prove the lock for {name}", path))
                continue
            repository_issue = _verify_repository_lock(name, commit, root)
            if repository_issue is not None:
                issues.append(ValidationIssue(repository_issue.code, repository_issue.message, path))

    test_contract = contract.get("test_contract")
    if isinstance(test_contract, dict):
        relative = str(test_contract.get("path", ""))
        expected_hash = str(test_contract.get("sha256", ""))
        if not _safe_path(relative):
            issues.append(ValidationIssue("UNSAFE_TEST_CONTRACT_PATH", "test_contract.path must be a normalized safe relative path", "$.test_contract.path"))
        if not _SHA256.fullmatch(expected_hash) or set(expected_hash) == {"0"}:
            issues.append(ValidationIssue("UNLOCKED_TEST_CONTRACT", "test_contract.sha256 requires a concrete SHA-256", "$.test_contract.sha256"))
        if base_dir is None:
            gaps.append(ValidationIssue("TASK_BASE_DIR_REQUIRED", "base_dir is required to verify the locked test contract", "$.test_contract"))
        elif _safe_path(relative):
            try:
                payload = _read_regular_bytes(base_dir, relative)
            except FileNotFoundError:
                gaps.append(ValidationIssue("TEST_CONTRACT_NOT_FOUND", f"Locked test contract not found: {relative}", "$.test_contract.path"))
            except OSError as exc:
                gaps.append(ValidationIssue("TEST_CONTRACT_UNREADABLE", f"Cannot read locked test contract: {exc}", "$.test_contract.path"))
            except (ValueError, RepositoryPathError) as exc:
                issues.append(ValidationIssue("UNSAFE_TEST_CONTRACT_PATH", str(exc), "$.test_contract.path"))
            else:
                actual_hash = hashlib.sha256(payload).hexdigest()
                if _SHA256.fullmatch(expected_hash) and actual_hash.lower() != expected_hash.lower():
                    issues.append(ValidationIssue("TEST_CONTRACT_HASH_MISMATCH", "Locked test contract hash does not match file content", "$.test_contract.sha256"))

    if executor_policy is not None:
        execution = executor_policy.get("execution", {}) if isinstance(executor_policy.get("execution"), dict) else {}
        caps = contract.get("capabilities", {}) if isinstance(contract.get("capabilities"), dict) else {}
        if execution.get("default_network") is False and caps.get("network") is not False:
            issues.append(ValidationIssue("POLICY_PRECEDENCE_VIOLATION", "Task cannot enable network denied by executor policy", "$.capabilities.network"))
        policy_secrets = set(execution.get("default_secrets", [])) if isinstance(execution.get("default_secrets"), list) else set()
        task_secrets = set(caps.get("secrets", [])) if isinstance(caps.get("secrets"), list) else set()
        if not task_secrets.issubset(policy_secrets):
            issues.append(ValidationIssue("POLICY_PRECEDENCE_VIOLATION", "Task requests secrets denied by executor policy", "$.capabilities.secrets"))
        if execution.get("auto_merge") is False and contract.get("merge_policy", {}).get("mode") != "PR_ONLY":
            issues.append(ValidationIssue("POLICY_PRECEDENCE_VIOLATION", "Task cannot enable merge denied by executor policy", "$.merge_policy.mode"))

    if issues:
        return ValidationResult(ValidationStatus.INVALID, issues + gaps, contract, authoritative=True)
    if gaps:
        return ValidationResult(ValidationStatus.INSUFFICIENT_EVIDENCE, gaps, contract, authoritative=True)
    return ValidationResult(ValidationStatus.VALID, normalized=contract, authoritative=True)
