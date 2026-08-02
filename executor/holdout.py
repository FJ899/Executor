from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


HoldoutFinding = tuple[str, str, str]


def _safe_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _resolve_holdout(base_dir: str | Path, location: str) -> tuple[Path, bytes]:
    root = Path(base_dir).resolve(strict=True)
    candidate = root / location
    if candidate.is_symlink():
        raise ValueError("Holdout file cannot be a symlink")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Holdout file escapes base_dir") from exc
    if not resolved.is_file():
        raise FileNotFoundError(location)
    payload = resolved.read_bytes()
    if not payload:
        raise RuntimeError("Holdout file is empty")
    if b"PLACEHOLDER" in payload.upper():
        raise RuntimeError("Holdout file is a placeholder")
    return resolved, payload


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
        issues.append(("UNSAFE_HOLDOUT_PATH", "Holdout path must be safe and relative", "$.holdout.location"))
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
    except ValueError as exc:
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
    elif verifier_role != "INDEPENDENT_HOLDOUT_VERIFIER":
        issues.append(("INVALID_HOLDOUT_VERIFIER", "Holdout evidence must come from an independent holdout verifier", "$.holdout"))
    return issues, gaps
