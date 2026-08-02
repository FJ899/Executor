from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from executor.repository_access import RepositoryPathError, canonical_repository_path, read_repository_bytes, validate_repository_candidate


HoldoutFinding = tuple[str, str, str]


def _safe_path(value: str) -> bool:
    try:
        canonical_repository_path(value)
    except RepositoryPathError:
        return False
    return True


def _resolve_holdout(base_dir: str | Path, location: str) -> tuple[str, bytes]:
    _, candidate = validate_repository_candidate(base_dir, location)
    if not candidate.exists():
        raise FileNotFoundError(location)
    canonical, payload = read_repository_bytes(base_dir, location)
    if not payload:
        raise RuntimeError("Holdout file is empty")
    if b"PLACEHOLDER" in payload.upper():
        raise RuntimeError("Holdout file is a placeholder")
    return canonical, payload


def verify_holdout(
    *,
    test_id: str,
    holdout: dict[str, Any],
    base_dir: str | Path | None,
    evidence: dict[str, Any] | None,
) -> tuple[list[HoldoutFinding], list[HoldoutFinding]]:
    issues: list[HoldoutFinding] = []
    gaps: list[HoldoutFinding] = []
    location = str(holdout.get("location", ""))
    if not _safe_path(location):
        issues.append(("UNSAFE_HOLDOUT_PATH", "Holdout path must be a normalized safe relative path", "$.holdout.location"))
        return issues, gaps
    if base_dir is None:
        gaps.append(("HOLDOUT_BASE_DIR_REQUIRED", "base_dir is required to inspect the holdout artifact", "$.holdout.location"))
        return issues, gaps
    try:
        _, payload = _resolve_holdout(base_dir, location)
    except FileNotFoundError:
        gaps.append(("HOLDOUT_NOT_FOUND", f"Holdout file not found: {location}", "$.holdout.location"))
        return issues, gaps
    except OSError as exc:
        gaps.append(("HOLDOUT_UNREADABLE", f"Cannot read holdout file: {exc}", "$.holdout.location"))
        return issues, gaps
    except (ValueError, RepositoryPathError) as exc:
        issues.append(("UNSAFE_HOLDOUT_PATH", str(exc), "$.holdout.location"))
        return issues, gaps
    except RuntimeError as exc:
        gaps.append(("HOLDOUT_CONTENT_UNUSABLE", str(exc), "$.holdout.location"))
        return issues, gaps

    artifact_sha256 = hashlib.sha256(payload).hexdigest()
    if evidence is None:
        gaps.append(("HOLDOUT_VISIBILITY_UNVERIFIED", "External holdout evidence is required; the contract declaration and local file cannot prove hiddenness", "$.holdout"))
        return issues, gaps
    if not isinstance(evidence, dict):
        issues.append(("INVALID_HOLDOUT_EVIDENCE", "Holdout evidence must be an object", "$.holdout"))
        return issues, gaps

    expected = {
        "schema_version": "executor-holdout-evidence/1.0",
        "test_id": test_id,
        "location": location,
        "artifact_sha256": artifact_sha256,
        "visibility": "HIDDEN_FROM_IMPLEMENTER",
        "access": "REPLAY_ONLY",
    }
    mismatches = {key: {"expected": value, "actual": evidence.get(key)} for key, value in expected.items() if evidence.get(key) != value}
    if mismatches:
        issues.append(("HOLDOUT_EVIDENCE_MISMATCH", f"Holdout evidence does not bind the declared artifact: {mismatches}", "$.holdout"))

    if not str(evidence.get("attestation_id", "")).strip() or not str(evidence.get("verifier", "")).strip():
        issues.append(("INVALID_HOLDOUT_EVIDENCE", "Holdout evidence requires attestation_id and verifier", "$.holdout"))
    verifier_role = evidence.get("verifier_role")
    if verifier_role == "TEST_FIXTURE_VERIFIER":
        if not test_id.startswith("EXECUTOR_VALIDATOR_FIXTURE-"):
            issues.append(("INVALID_HOLDOUT_VERIFIER", "TEST_FIXTURE_VERIFIER is allowed only for validator fixture contracts", "$.holdout"))
    elif verifier_role == "INDEPENDENT_HOLDOUT_VERIFIER":
        gaps.append(("INDEPENDENT_HOLDOUT_VERIFICATION_UNAVAILABLE", "The independent verifier trust mechanism is not implemented yet; a role string cannot prove independence", "$.holdout"))
    else:
        issues.append(("INVALID_HOLDOUT_VERIFIER", "Unsupported holdout verifier role", "$.holdout"))
    return issues, gaps
