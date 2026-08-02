from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from typing import Any

from executor.contracts import ValidationIssue, ValidationStatus
from executor.repository_access import (
    RepositoryPathError,
    canonical_repository_path,
    validate_scope_pattern,
)


_PACKET_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_HEX_COMMIT = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_ACTION_KINDS = {
    "SANDBOX_EXECUTION",
    "WRITE_REPOSITORY",
    "CREATE_PULL_REQUEST",
    "MERGE_PULL_REQUEST",
    "EXTERNAL_PROJECT_EXECUTION",
}
_ISSUER_ROLES = {"USER", "POLICY_VERIFIER"}
_RISK_CLASSES = {"LOW_RISK", "MEDIUM_RISK", "HIGH_RISK"}
_MODES = {"PLAN", "BUILD_AND_TEST", "AUDIT"}


@dataclass(frozen=True)
class AuthorizationContext:
    run_id: str
    task_id: str
    risk_class: str
    mode: str
    executor_commit: str
    policy_sha256: str
    project_contract_sha256: str
    task_contract_sha256: str
    test_contract_sha256: str
    repository_commits: dict[str, str]
    allowed_paths: tuple[str, ...]
    external_projects: bool
    auto_merge: bool
    default_network: bool
    default_secrets: tuple[str, ...]
    verified_issuer_evidence: dict[str, tuple[str, str]]


@dataclass(frozen=True)
class AuthorizationDecision:
    packet_id: str
    payload_sha256: str
    action_kind: str
    expires_at: str
    issuer_role: str
    issuer_id: str
    issuer_evidence_ref: str
    ready_for_atomic_consumption: bool = True


@dataclass(frozen=True)
class AuthorizationValidationResult:
    status: ValidationStatus
    issues: tuple[ValidationIssue, ...]
    normalized: dict[str, Any] | None = None

    @property
    def eligible_for_consumption(self) -> bool:
        return self.status == ValidationStatus.VALID

    @property
    def action_status(self) -> str:
        return (
            "READY_FOR_ATOMIC_CONSUMPTION"
            if self.eligible_for_consumption
            else "BLOCKED_BEFORE_ACTION"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "action_status": self.action_status,
            "eligible_for_consumption": self.eligible_for_consumption,
            "issues": [issue.__dict__ for issue in self.issues],
            "normalized": self.normalized,
        }


def canonical_packet_payload(packet: dict[str, Any]) -> bytes:
    if not isinstance(packet, dict):
        raise ValueError("Authorization packet must be an object")
    payload = {key: value for key, value in packet.items() if key != "integrity"}
    try:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Authorization packet is not canonical JSON: {exc}") from exc
    return text.encode("utf-8")


def packet_payload_sha256(packet: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_packet_payload(packet)).hexdigest()


def _invalid(
    issues: list[ValidationIssue], packet: dict[str, Any] | None
) -> tuple[AuthorizationValidationResult, None]:
    return (
        AuthorizationValidationResult(
            ValidationStatus.INVALID,
            tuple(issues),
            packet,
        ),
        None,
    )


def _parse_utc(
    value: object,
    *,
    path: str,
    issues: list[ValidationIssue],
) -> datetime | None:
    if not isinstance(value, str) or not value.endswith("Z"):
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_TIME",
                "Timestamp must be RFC3339 UTC ending in Z",
                path,
            )
        )
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_TIME",
                "Timestamp must be valid RFC3339 UTC",
                path,
            )
        )
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_TIME",
                "Timestamp must be UTC",
                path,
            )
        )
        return None
    return parsed.astimezone(timezone.utc)


def _object(
    value: object,
    *,
    path: str,
    issues: list[ValidationIssue],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_PACKET",
                "Expected an object",
                path,
            )
        )
        return None
    return value


def _exact_keys(
    value: dict[str, Any],
    expected: set[str],
    *,
    path: str,
    issues: list[ValidationIssue],
) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    additional = sorted(actual - expected)
    if missing or additional:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_PACKET",
                f"Object keys differ; missing={missing}, additional={additional}",
                path,
            )
        )


def _hash_field(
    value: object,
    *,
    path: str,
    issues: list[ValidationIssue],
) -> str:
    text = value if isinstance(value, str) else ""
    if _SHA256.fullmatch(text) is None or set(text) == {"0"}:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_BINDING",
                "Expected a concrete SHA-256",
                path,
            )
        )
    return text.lower()


def _commit_field(
    value: object,
    *,
    path: str,
    issues: list[ValidationIssue],
) -> str:
    text = value if isinstance(value, str) else ""
    if _HEX_COMMIT.fullmatch(text) is None or set(text) == {"0"}:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_BINDING",
                "Expected a concrete commit hash",
                path,
            )
        )
    return text.lower()


def _requires_user(action: dict[str, Any], context: AuthorizationContext) -> bool:
    return (
        context.risk_class == "HIGH_RISK"
        or action.get("kind") in {
            "MERGE_PULL_REQUEST",
            "EXTERNAL_PROJECT_EXECUTION",
        }
        or action.get("external_project") is True
        or action.get("network") is True
        or bool(action.get("secrets"))
    )


def _validate_context(
    context: AuthorizationContext,
    issues: list[ValidationIssue],
) -> None:
    if _PACKET_ID.fullmatch(context.run_id) is None:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_CONTEXT",
                "Context run_id is invalid",
                "$.run_id",
            )
        )
    if not context.task_id:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_CONTEXT",
                "Context task_id is required",
                "$.bindings.task_id",
            )
        )
    if context.risk_class not in _RISK_CLASSES or context.mode not in _MODES:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_CONTEXT",
                "Context risk_class or mode is unsupported",
                "$.bindings",
            )
        )
    for value, path, pattern in (
        (context.executor_commit, "$.bindings.executor_commit", _HEX_COMMIT),
        (context.policy_sha256, "$.bindings.policy_sha256", _SHA256),
        (
            context.project_contract_sha256,
            "$.bindings.project_contract_sha256",
            _SHA256,
        ),
        (
            context.task_contract_sha256,
            "$.bindings.task_contract_sha256",
            _SHA256,
        ),
        (
            context.test_contract_sha256,
            "$.bindings.test_contract_sha256",
            _SHA256,
        ),
    ):
        if pattern.fullmatch(value) is None or set(value) == {"0"}:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CONTEXT",
                    "Context contains an invalid immutable binding",
                    path,
                )
            )
    if not context.repository_commits:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_CONTEXT",
                "Context repository_commits cannot be empty",
                "$.bindings.repository_commits",
            )
        )
    for name, commit in context.repository_commits.items():
        if not name or _HEX_COMMIT.fullmatch(commit) is None or set(commit) == {"0"}:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CONTEXT",
                    "Context repository binding is invalid",
                    f"$.bindings.repository_commits.{name}",
                )
            )
    try:
        for pattern in context.allowed_paths:
            validate_scope_pattern(pattern)
    except RepositoryPathError as exc:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_CONTEXT",
                str(exc),
                "$.action.paths",
            )
        )
    for evidence_ref, binding in context.verified_issuer_evidence.items():
        if (
            not evidence_ref
            or not isinstance(binding, tuple)
            or len(binding) != 2
            or binding[0] not in _ISSUER_ROLES
            or not binding[1]
        ):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CONTEXT",
                    "Verified issuer evidence binding is invalid",
                    "$.issuer",
                )
            )


def validate_action_authorization_packet(
    packet: dict[str, Any],
    *,
    context: AuthorizationContext,
    now: datetime | None = None,
    consumed_packet_ids: set[str] | None = None,
) -> tuple[AuthorizationValidationResult, AuthorizationDecision | None]:
    issues: list[ValidationIssue] = []
    _validate_context(context, issues)
    if not isinstance(packet, dict):
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_PACKET",
                "Packet must be an object",
            )
        )
        return _invalid(issues, None)

    _exact_keys(
        packet,
        {
            "schema_version",
            "packet_id",
            "run_id",
            "issued_at",
            "expires_at",
            "issuer",
            "bindings",
            "action",
            "decision",
            "constraints",
            "integrity",
        },
        path="$",
        issues=issues,
    )
    if packet.get("schema_version") != "executor-action-authorization/1.0":
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_SCHEMA",
                "schema_version must be executor-action-authorization/1.0",
                "$.schema_version",
            )
        )

    packet_id = packet.get("packet_id")
    if not isinstance(packet_id, str) or _PACKET_ID.fullmatch(packet_id) is None:
        issues.append(
            ValidationIssue(
                "INVALID_AUTHORIZATION_PACKET_ID",
                "packet_id must use 1-128 safe ASCII characters",
                "$.packet_id",
            )
        )
        packet_id = ""
    if packet_id in (consumed_packet_ids or set()):
        issues.append(
            ValidationIssue(
                "AUTHORIZATION_REPLAY",
                "Authorization packet was already consumed",
                "$.packet_id",
            )
        )
    if packet.get("run_id") != context.run_id:
        issues.append(
            ValidationIssue(
                "AUTHORIZATION_CONTEXT_MISMATCH",
                "run_id does not match the active run",
                "$.run_id",
            )
        )

    issued_at = _parse_utc(
        packet.get("issued_at"), path="$.issued_at", issues=issues
    )
    expires_at = _parse_utc(
        packet.get("expires_at"), path="$.expires_at", issues=issues
    )
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if issued_at is not None and issued_at > current + timedelta(minutes=5):
        issues.append(
            ValidationIssue(
                "AUTHORIZATION_NOT_YET_VALID",
                "issued_at is in the future",
                "$.issued_at",
            )
        )
    if expires_at is not None and expires_at <= current:
        issues.append(
            ValidationIssue(
                "AUTHORIZATION_EXPIRED",
                "Authorization packet has expired",
                "$.expires_at",
            )
        )
    lifetime: timedelta | None = None
    if issued_at is not None and expires_at is not None:
        lifetime = expires_at - issued_at
        if lifetime <= timedelta(0) or lifetime > timedelta(hours=24):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_LIFETIME",
                    "Authorization lifetime must be greater than 0 and at most 24 hours",
                    "$.expires_at",
                )
            )

    issuer = _object(packet.get("issuer"), path="$.issuer", issues=issues)
    issuer_role = ""
    issuer_id = ""
    evidence_ref = ""
    if issuer is not None:
        _exact_keys(
            issuer,
            {"role", "id", "evidence_ref"},
            path="$.issuer",
            issues=issues,
        )
        issuer_role = issuer.get("role") if isinstance(issuer.get("role"), str) else ""
        issuer_id = issuer.get("id") if isinstance(issuer.get("id"), str) else ""
        evidence_ref = (
            issuer.get("evidence_ref")
            if isinstance(issuer.get("evidence_ref"), str)
            else ""
        )
        if issuer_role not in _ISSUER_ROLES or not issuer_id or not evidence_ref:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ISSUER",
                    "Issuer role, id and evidence_ref are required",
                    "$.issuer",
                )
            )
        verified = context.verified_issuer_evidence.get(evidence_ref)
        if verified != (issuer_role, issuer_id):
            issues.append(
                ValidationIssue(
                    "UNVERIFIED_AUTHORIZATION_ISSUER",
                    "Packet issuer is not bound to verified external evidence",
                    "$.issuer",
                )
            )

    bindings = _object(packet.get("bindings"), path="$.bindings", issues=issues)
    if bindings is not None:
        _exact_keys(
            bindings,
            {
                "task_id",
                "risk_class",
                "mode",
                "executor_commit",
                "policy_sha256",
                "project_contract_sha256",
                "task_contract_sha256",
                "test_contract_sha256",
                "repository_commits",
            },
            path="$.bindings",
            issues=issues,
        )
        expected_scalar = {
            "task_id": context.task_id,
            "risk_class": context.risk_class,
            "mode": context.mode,
            "executor_commit": context.executor_commit.lower(),
            "policy_sha256": context.policy_sha256.lower(),
            "project_contract_sha256": context.project_contract_sha256.lower(),
            "task_contract_sha256": context.task_contract_sha256.lower(),
            "test_contract_sha256": context.test_contract_sha256.lower(),
        }
        actual_scalar = {
            "task_id": bindings.get("task_id"),
            "risk_class": bindings.get("risk_class"),
            "mode": bindings.get("mode"),
            "executor_commit": _commit_field(
                bindings.get("executor_commit"),
                path="$.bindings.executor_commit",
                issues=issues,
            ),
            "policy_sha256": _hash_field(
                bindings.get("policy_sha256"),
                path="$.bindings.policy_sha256",
                issues=issues,
            ),
            "project_contract_sha256": _hash_field(
                bindings.get("project_contract_sha256"),
                path="$.bindings.project_contract_sha256",
                issues=issues,
            ),
            "task_contract_sha256": _hash_field(
                bindings.get("task_contract_sha256"),
                path="$.bindings.task_contract_sha256",
                issues=issues,
            ),
            "test_contract_sha256": _hash_field(
                bindings.get("test_contract_sha256"),
                path="$.bindings.test_contract_sha256",
                issues=issues,
            ),
        }
        if actual_scalar != expected_scalar:
            issues.append(
                ValidationIssue(
                    "AUTHORIZATION_CONTEXT_MISMATCH",
                    "Packet scalar bindings do not match active context",
                    "$.bindings",
                )
            )
        repositories = bindings.get("repository_commits")
        if not isinstance(repositories, dict) or not repositories:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_BINDING",
                    "repository_commits must be a non-empty object",
                    "$.bindings.repository_commits",
                )
            )
        else:
            normalized_repositories = {
                str(name): _commit_field(
                    commit,
                    path=f"$.bindings.repository_commits.{name}",
                    issues=issues,
                )
                for name, commit in repositories.items()
            }
            expected_repositories = {
                name: commit.lower()
                for name, commit in context.repository_commits.items()
            }
            if normalized_repositories != expected_repositories:
                issues.append(
                    ValidationIssue(
                        "AUTHORIZATION_CONTEXT_MISMATCH",
                        "Repository commit bindings do not match active context",
                        "$.bindings.repository_commits",
                    )
                )

    action = _object(packet.get("action"), path="$.action", issues=issues)
    action_kind = ""
    if action is not None:
        _exact_keys(
            action,
            {"kind", "argv", "paths", "network", "secrets", "external_project"},
            path="$.action",
            issues=issues,
        )
        action_kind = action.get("kind") if isinstance(action.get("kind"), str) else ""
        if action_kind not in _ACTION_KINDS:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "Unsupported action kind",
                    "$.action.kind",
                )
            )
        argv = action.get("argv")
        if not isinstance(argv, list) or not all(
            isinstance(item, str) and item and "\x00" not in item for item in argv
        ):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "argv must be a list of non-empty NUL-free strings",
                    "$.action.argv",
                )
            )
        if action_kind in {"SANDBOX_EXECUTION", "EXTERNAL_PROJECT_EXECUTION"} and not argv:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "Executable action requires non-empty argv",
                    "$.action.argv",
                )
            )

        paths = action.get("paths")
        normalized_paths: list[str] = []
        if not isinstance(paths, list) or not all(
            isinstance(item, str) and item for item in paths
        ):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "paths must be a list of non-empty strings",
                    "$.action.paths",
                )
            )
        else:
            for index, path in enumerate(paths):
                try:
                    normalized_paths.append(canonical_repository_path(path))
                except RepositoryPathError as exc:
                    issues.append(
                        ValidationIssue(
                            "INVALID_AUTHORIZATION_PATH",
                            str(exc),
                            f"$.action.paths[{index}]",
                        )
                    )
            if len(normalized_paths) != len(set(normalized_paths)):
                issues.append(
                    ValidationIssue(
                        "INVALID_AUTHORIZATION_ACTION",
                        "Canonical action paths must be unique",
                        "$.action.paths",
                    )
                )
            try:
                allowed_patterns = tuple(
                    validate_scope_pattern(pattern)
                    for pattern in context.allowed_paths
                )
            except RepositoryPathError:
                allowed_patterns = ()
            for index, path in enumerate(normalized_paths):
                if not any(fnmatch(path, pattern) for pattern in allowed_patterns):
                    issues.append(
                        ValidationIssue(
                            "AUTHORIZATION_PATH_OUT_OF_SCOPE",
                            f"Path is outside task scope: {path}",
                            f"$.action.paths[{index}]",
                        )
                    )

        network = action.get("network")
        external_project = action.get("external_project")
        if not isinstance(network, bool) or not isinstance(external_project, bool):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "network and external_project must be boolean",
                    "$.action",
                )
            )
        secrets = action.get("secrets")
        if (
            not isinstance(secrets, list)
            or not all(isinstance(item, str) and item for item in secrets)
            or len(set(secrets or [])) != len(secrets or [])
        ):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "secrets must be a unique list of non-empty names",
                    "$.action.secrets",
                )
            )
        elif not set(secrets).issubset(context.default_secrets):
            issues.append(
                ValidationIssue(
                    "AUTHORIZATION_CAPABILITY_DENIED",
                    "Packet requests secrets denied by policy",
                    "$.action.secrets",
                )
            )
        if network is True and not context.default_network:
            issues.append(
                ValidationIssue(
                    "AUTHORIZATION_CAPABILITY_DENIED",
                    "Packet requests network denied by policy",
                    "$.action.network",
                )
            )
        if external_project is True and not context.external_projects:
            issues.append(
                ValidationIssue(
                    "AUTHORIZATION_CAPABILITY_DENIED",
                    "Packet requests external project execution denied by policy",
                    "$.action.external_project",
                )
            )
        if action_kind == "EXTERNAL_PROJECT_EXECUTION" and external_project is not True:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "EXTERNAL_PROJECT_EXECUTION requires external_project=true",
                    "$.action.external_project",
                )
            )
        if action_kind != "EXTERNAL_PROJECT_EXECUTION" and external_project is True:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_ACTION",
                    "external_project=true requires EXTERNAL_PROJECT_EXECUTION",
                    "$.action.external_project",
                )
            )
        if action_kind == "MERGE_PULL_REQUEST" and context.auto_merge:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CONTEXT",
                    "Terminal packet authorizes explicit merge, not auto-merge",
                    "$.action.kind",
                )
            )
        if issuer_role and _requires_user(action, context) and issuer_role != "USER":
            issues.append(
                ValidationIssue(
                    "USER_AUTHORIZATION_REQUIRED",
                    "This action requires a verified USER-issued packet",
                    "$.issuer.role",
                )
            )

    decision = _object(packet.get("decision"), path="$.decision", issues=issues)
    if decision is not None:
        _exact_keys(
            decision,
            {"status", "reasons"},
            path="$.decision",
            issues=issues,
        )
        if decision.get("status") != "AUTHORIZED":
            issues.append(
                ValidationIssue(
                    "AUTHORIZATION_DENIED",
                    "Packet decision is not AUTHORIZED",
                    "$.decision.status",
                )
            )
        reasons = decision.get("reasons")
        if (
            not isinstance(reasons, list)
            or not reasons
            or not all(isinstance(item, str) and item.strip() for item in reasons)
        ):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_DECISION",
                    "At least one non-empty reason is required",
                    "$.decision.reasons",
                )
            )

    constraints = _object(
        packet.get("constraints"), path="$.constraints", issues=issues
    )
    if constraints is not None:
        _exact_keys(
            constraints,
            {"max_uses", "max_duration_seconds", "manual_confirmation_required"},
            path="$.constraints",
            issues=issues,
        )
        max_uses = constraints.get("max_uses")
        if type(max_uses) is not int or max_uses != 1:
            issues.append(
                ValidationIssue(
                    "AUTHORIZATION_MUST_BE_ONE_TIME",
                    "max_uses must be the integer 1",
                    "$.constraints.max_uses",
                )
            )
        duration = constraints.get("max_duration_seconds")
        if type(duration) is not int or duration <= 0 or duration > 86400:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CONSTRAINT",
                    "max_duration_seconds must be an integer in 1..86400",
                    "$.constraints.max_duration_seconds",
                )
            )
        elif lifetime is not None and lifetime > timedelta(seconds=duration):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CONSTRAINT",
                    "Packet lifetime exceeds max_duration_seconds",
                    "$.constraints.max_duration_seconds",
                )
            )
        manual_required = constraints.get("manual_confirmation_required")
        if not isinstance(manual_required, bool):
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CONSTRAINT",
                    "manual_confirmation_required must be boolean",
                    "$.constraints.manual_confirmation_required",
                )
            )
        if action_kind == "MERGE_PULL_REQUEST" and manual_required is not True:
            issues.append(
                ValidationIssue(
                    "MANUAL_CONFIRMATION_REQUIRED",
                    "Merge authorization requires manual_confirmation_required=true",
                    "$.constraints.manual_confirmation_required",
                )
            )

    integrity = _object(packet.get("integrity"), path="$.integrity", issues=issues)
    actual_hash = ""
    if integrity is not None:
        _exact_keys(
            integrity,
            {"algorithm", "payload_sha256"},
            path="$.integrity",
            issues=issues,
        )
        if integrity.get("algorithm") != "SHA-256":
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_INTEGRITY",
                    "Only SHA-256 is supported",
                    "$.integrity.algorithm",
                )
            )
        expected_hash = (
            integrity.get("payload_sha256", "")
            if isinstance(integrity.get("payload_sha256"), str)
            else ""
        ).lower()
        try:
            actual_hash = packet_payload_sha256(packet)
        except ValueError as exc:
            issues.append(
                ValidationIssue(
                    "INVALID_AUTHORIZATION_CANONICAL_JSON",
                    str(exc),
                    "$",
                )
            )
        if _SHA256.fullmatch(expected_hash) is None or (
            actual_hash and expected_hash != actual_hash
        ):
            issues.append(
                ValidationIssue(
                    "AUTHORIZATION_INTEGRITY_MISMATCH",
                    "Packet payload hash does not match canonical content",
                    "$.integrity.payload_sha256",
                )
            )

    if issues:
        return _invalid(issues, packet)
    assert expires_at is not None
    authorization = AuthorizationDecision(
        packet_id=packet_id,
        payload_sha256=actual_hash,
        action_kind=action_kind,
        expires_at=expires_at.isoformat().replace("+00:00", "Z"),
        issuer_role=issuer_role,
        issuer_id=issuer_id,
        issuer_evidence_ref=evidence_ref,
    )
    return (
        AuthorizationValidationResult(
            ValidationStatus.VALID,
            (),
            packet,
        ),
        authorization,
    )
