from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ContractLoadError(Exception):
    pass


class ValidationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str = "$"


@dataclass
class ValidationResult:
    status: ValidationStatus
    issues: list[ValidationIssue] = field(default_factory=list)
    normalized: dict[str, Any] | None = None

    @property
    def execution_status(self) -> str:
        return "READY_FOR_MODEL" if self.status == ValidationStatus.VALID else "BLOCKED_BEFORE_MODEL"

    @property
    def ok(self) -> bool:
        return self.status == ValidationStatus.VALID

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status.value, "execution_status": self.execution_status, "issues": [x.__dict__ for x in self.issues], "normalized": self.normalized}


def load_contract(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractLoadError(f"Cannot read contract {p}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractLoadError(f"{p} must use JSON-compatible YAML: {exc.msg} at line {exc.lineno}") from exc
    if not isinstance(data, dict):
        raise ContractLoadError(f"{p} must contain an object")
    return data


def _safe_path(value: str) -> bool:
    path = Path(value)
    return bool(value) and not path.is_absolute() and ".." not in path.parts


def _mapping(value: object) -> bool:
    return isinstance(value, dict)


def _nonempty_list(value: object) -> bool:
    return isinstance(value, list) and bool(value)


_ASSERTION = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(==|!=)\s*(.+?)\s*$")
_SELECTOR_TOKEN = re.compile(r"(?:\.([A-Za-z_][A-Za-z0-9_-]*)|\[(0|[1-9][0-9]*)\])")


class _SelectorSyntaxError(ValueError):
    pass


class _SelectorLookupError(LookupError):
    pass


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_nonstandard_json_constant(value: str) -> None:
    raise ValueError(f"Non-standard JSON constant: {value}")


def _load_evidence_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_json_keys,
        parse_constant=_reject_nonstandard_json_constant,
    )


def _selector_tokens(selector: str) -> list[str | int]:
    if not selector.startswith("$"):
        raise _SelectorSyntaxError("Selector must start with $")
    tokens: list[str | int] = []
    position = 1
    while position < len(selector):
        match = _SELECTOR_TOKEN.match(selector, position)
        if match is None:
            raise _SelectorSyntaxError("Only .field and [index] selector segments are supported")
        key, index = match.groups()
        tokens.append(key if key is not None else int(index))
        position = match.end()
    return tokens


def _select_json(value: Any, tokens: list[str | int]) -> Any:
    selected = value
    for token in tokens:
        if isinstance(token, str):
            if not isinstance(selected, dict) or token not in selected:
                raise _SelectorLookupError(f"Object field not found: {token}")
            selected = selected[token]
        else:
            if not isinstance(selected, list) or token >= len(selected):
                raise _SelectorLookupError(f"Array index not found: {token}")
            selected = selected[token]
    return selected


def _parse_assertion(text: str) -> tuple[str, str, Any, str] | None:
    match = _ASSERTION.match(text)
    if match is None:
        return None
    field, operator, literal = match.groups()
    literal = literal.strip()
    try:
        value = _load_evidence_json(literal)
    except (json.JSONDecodeError, ValueError):
        value = literal
    return field, operator, value, literal


def _claim_expected_value(text: str) -> tuple[str, Any] | None:
    parsed = _parse_assertion(text)
    if parsed is None:
        return None
    _, operator, expected, _ = parsed
    return operator, expected


def _json_values_equal(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return actual == expected
    if isinstance(actual, dict) or isinstance(expected, dict):
        if not isinstance(actual, dict) or not isinstance(expected, dict) or actual.keys() != expected.keys():
            return False
        return all(_json_values_equal(actual[key], expected[key]) for key in actual)
    if isinstance(actual, list) or isinstance(expected, list):
        if not isinstance(actual, list) or not isinstance(expected, list) or len(actual) != len(expected):
            return False
        return all(_json_values_equal(left, right) for left, right in zip(actual, expected, strict=True))
    return type(actual) is type(expected) and actual == expected


def _resolve_source_file(base_dir: str | Path, filename: str) -> Path:
    root = Path(base_dir).resolve(strict=True)
    candidate = root / filename
    if candidate.is_symlink():
        raise ValueError("Source file cannot be a symlink")
    resolved = candidate.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Source file escapes base_dir") from exc
    if not resolved.is_file():
        raise FileNotFoundError(filename)
    return resolved


def _control(contract: dict[str, Any], name: str, issues: list[ValidationIssue]) -> None:
    value = contract.get(name)
    if not _mapping(value):
        issues.append(ValidationIssue("MISSING_CONTROL", f"{name} must be an object", f"$.{name}"))
        return
    if not str(value.get("description", "")).strip():
        issues.append(ValidationIssue("MISSING_DESCRIPTION", f"{name}.description is required", f"$.{name}.description"))
    if not str(value.get("expected", "")).strip():
        issues.append(ValidationIssue("MISSING_EXPECTED", f"{name}.expected is required", f"$.{name}.expected"))


def _contradictions(assertions: list[str]) -> list[ValidationIssue]:
    equal: dict[str, list[tuple[Any, str]]] = {}
    not_equal: dict[str, list[tuple[Any, str]]] = {}
    issues: list[ValidationIssue] = []
    for index, text in enumerate(assertions):
        parsed = _parse_assertion(text)
        if parsed is None:
            continue
        field, operator, value, literal = parsed
        if operator == "==":
            for previous, previous_literal in equal.get(field, []):
                if not _json_values_equal(previous, value):
                    issues.append(ValidationIssue("CONTRADICTORY_ACCEPTANCE", f"{field} cannot equal both {previous_literal} and {literal}", f"$.acceptance[{index}]"))
            for denied, denied_literal in not_equal.get(field, []):
                if _json_values_equal(denied, value):
                    issues.append(ValidationIssue("CONTRADICTORY_ACCEPTANCE", f"{field} is required to equal {literal} and not equal {denied_literal}", f"$.acceptance[{index}]"))
            equal.setdefault(field, []).append((value, literal))
        else:
            for required, required_literal in equal.get(field, []):
                if _json_values_equal(required, value):
                    issues.append(ValidationIssue("CONTRADICTORY_ACCEPTANCE", f"{field} is required to equal {required_literal} and not equal {literal}", f"$.acceptance[{index}]"))
            not_equal.setdefault(field, []).append((value, literal))
    return issues


def validate_test_contract(contract: dict[str, Any], *, base_dir: str | Path | None = None) -> ValidationResult:
    issues: list[ValidationIssue] = []
    gaps: list[ValidationIssue] = []
    if contract.get("schema_version") != "executor-test/1.0":
        issues.append(ValidationIssue("INVALID_SCHEMA_VERSION", "schema_version must be executor-test/1.0", "$.schema_version"))
    if not str(contract.get("test_id", "")).strip():
        issues.append(ValidationIssue("MISSING_TEST_ID", "test_id is required", "$.test_id"))
    claims = contract.get("source_claims")
    if not _nonempty_list(claims):
        gaps.append(ValidationIssue("NO_SOURCE_CLAIMS", "At least one source claim is required", "$.source_claims"))
    else:
        for index, claim in enumerate(claims):
            source = claim.get("source") if _mapping(claim) else None
            claim_text = str(claim.get("claim", "")).strip() if _mapping(claim) else ""
            if not _mapping(claim) or not claim_text:
                gaps.append(ValidationIssue("INVALID_SOURCE_CLAIM", "Claim text is required", f"$.source_claims[{index}]"))
                continue
            claim_expectation = _claim_expected_value(claim_text)
            if claim_expectation is None:
                issues.append(ValidationIssue("UNSUPPORTED_SOURCE_CLAIM", "Source claim must use field == value or field != value", f"$.source_claims[{index}].claim"))
            if not _mapping(source):
                gaps.append(ValidationIssue("MISSING_SOURCE", "Claim source is required", f"$.source_claims[{index}].source"))
                continue
            filename = str(source.get("file", ""))
            selector = str(source.get("selector", ""))
            if not _safe_path(filename):
                issues.append(ValidationIssue("UNSAFE_SOURCE_PATH", "Source path must be safe and relative", f"$.source_claims[{index}].source.file"))
            if not selector:
                gaps.append(ValidationIssue("MISSING_SELECTOR", "Source selector is required", f"$.source_claims[{index}].source.selector"))
                selector_tokens = None
            else:
                try:
                    selector_tokens = _selector_tokens(selector)
                except _SelectorSyntaxError as exc:
                    issues.append(ValidationIssue("INVALID_SOURCE_SELECTOR", str(exc), f"$.source_claims[{index}].source.selector"))
                    selector_tokens = None
            if base_dir is None:
                gaps.append(ValidationIssue("SOURCE_BASE_DIR_REQUIRED", "base_dir is required to verify source claims", f"$.source_claims[{index}].source"))
            elif _safe_path(filename) and selector_tokens is not None and claim_expectation is not None:
                try:
                    source_path = _resolve_source_file(base_dir, filename)
                except FileNotFoundError:
                    gaps.append(ValidationIssue("SOURCE_FILE_NOT_FOUND", f"Source file not found: {filename}", f"$.source_claims[{index}].source.file"))
                    continue
                except OSError as exc:
                    gaps.append(ValidationIssue("SOURCE_FILE_UNREADABLE", f"Cannot read source file: {exc}", f"$.source_claims[{index}].source.file"))
                    continue
                except ValueError as exc:
                    issues.append(ValidationIssue("UNSAFE_SOURCE_PATH", str(exc), f"$.source_claims[{index}].source.file"))
                    continue
                try:
                    source_value = _load_evidence_json(source_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                    gaps.append(ValidationIssue("SOURCE_FILE_INVALID", f"Source file must contain readable JSON: {exc}", f"$.source_claims[{index}].source.file"))
                    continue
                try:
                    selected = _select_json(source_value, selector_tokens)
                except _SelectorLookupError as exc:
                    gaps.append(ValidationIssue("SOURCE_SELECTOR_NOT_FOUND", str(exc), f"$.source_claims[{index}].source.selector"))
                    continue
                operator, expected = claim_expectation
                equal = _json_values_equal(selected, expected)
                if (operator == "==" and not equal) or (operator == "!=" and equal):
                    gaps.append(ValidationIssue("SOURCE_CLAIM_MISMATCH", "Selected source value does not satisfy the claim", f"$.source_claims[{index}].claim"))
    for name in ("positive_control", "negative_control", "tamper_control"):
        _control(contract, name, issues)
    positive, negative = contract.get("positive_control", {}), contract.get("negative_control", {})
    if _mapping(positive) and _mapping(negative) and (positive.get("description") == negative.get("description") or positive.get("expected") == negative.get("expected")):
        issues.append(ValidationIssue("CONTROLS_NOT_DISTINCT", "Positive and negative controls must differ", "$.negative_control"))
    tamper = contract.get("tamper_control", {})
    if _mapping(tamper):
        if tamper.get("method") not in {"replay_hash_mismatch", "artifact_provenance", "immutable_input_hash"}:
            issues.append(ValidationIssue("INVALID_TAMPER_METHOD", "Tamper method is not deterministic", "$.tamper_control.method"))
        if tamper.get("expected") != "DETECTED":
            issues.append(ValidationIssue("TAMPER_MUST_BE_DETECTED", "Tamper control must expect DETECTED", "$.tamper_control.expected"))
    unchanged = contract.get("unchanged_controls")
    if not _nonempty_list(unchanged):
        issues.append(ValidationIssue("MISSING_UNCHANGED_CONTROL", "At least one unchanged control is required", "$.unchanged_controls"))
    else:
        for index, item in enumerate(unchanged):
            if not _mapping(item) or not str(item.get("name", "")).strip() or not str(item.get("assertion", "")).strip():
                issues.append(ValidationIssue("INVALID_UNCHANGED_CONTROL", "Each unchanged control needs name and assertion", f"$.unchanged_controls[{index}]"))
    holdout = contract.get("holdout")
    if not _mapping(holdout):
        issues.append(ValidationIssue("MISSING_HOLDOUT", "Holdout contract is required", "$.holdout"))
    else:
        if holdout.get("visibility") != "HIDDEN_FROM_IMPLEMENTER":
            issues.append(ValidationIssue("HOLDOUT_VISIBLE", "Holdout must be hidden", "$.holdout.visibility"))
        if holdout.get("access") != "REPLAY_ONLY":
            issues.append(ValidationIssue("INVALID_HOLDOUT_ACCESS", "Holdout access must be REPLAY_ONLY", "$.holdout.access"))
        location = str(holdout.get("location", ""))
        if not _safe_path(location):
            issues.append(ValidationIssue("UNSAFE_HOLDOUT_PATH", "Holdout path must be safe and relative", "$.holdout.location"))
        elif base_dir is not None and not (Path(base_dir) / location).is_file():
            gaps.append(ValidationIssue("HOLDOUT_NOT_FOUND", f"Holdout file not found: {location}", "$.holdout.location"))
    acceptance = contract.get("acceptance")
    if not _nonempty_list(acceptance) or not all(isinstance(x, str) and x.strip() for x in acceptance or []):
        issues.append(ValidationIssue("MISSING_ACCEPTANCE", "Acceptance needs non-empty assertions", "$.acceptance"))
    else:
        issues.extend(_contradictions(acceptance))
    if issues:
        return ValidationResult(ValidationStatus.INVALID, issues + gaps, contract)
    if gaps:
        return ValidationResult(ValidationStatus.INSUFFICIENT_EVIDENCE, gaps, contract)
    return ValidationResult(ValidationStatus.VALID, normalized=contract)


_PATH_CLASSES = {"semantic", "technical", "infrastructure", "generated", "test", "unknown"}
_APPROVALS = {"USER", "AI"}


def validate_project_contract(contract: dict[str, Any]) -> ValidationResult:
    issues: list[ValidationIssue] = []
    if contract.get("schema_version") != "executor-project/1.0":
        issues.append(ValidationIssue("INVALID_SCHEMA_VERSION", "schema_version must be executor-project/1.0", "$.schema_version"))
    project = contract.get("project")
    if not _mapping(project):
        issues.append(ValidationIssue("MISSING_PROJECT", "project object is required", "$.project"))
    else:
        for key in ("name", "repository", "entrypoint"):
            if not str(project.get(key, "")).strip():
                issues.append(ValidationIssue("MISSING_PROJECT_FIELD", f"project.{key} is required", f"$.project.{key}"))
        if str(project.get("entrypoint", "")) and not _safe_path(str(project["entrypoint"])):
            issues.append(ValidationIssue("UNSAFE_ENTRYPOINT", "entrypoint must be safe", "$.project.entrypoint"))
    sources = contract.get("authoritative_sources")
    roles = set()
    if not _nonempty_list(sources):
        issues.append(ValidationIssue("NO_AUTHORITATIVE_SOURCES", "At least one authoritative source is required", "$.authoritative_sources"))
    else:
        for index, source in enumerate(sources):
            if not _mapping(source) or not _safe_path(str(source.get("path", ""))):
                issues.append(ValidationIssue("INVALID_AUTHORITATIVE_SOURCE", "Source requires safe path", f"$.authoritative_sources[{index}]"))
                continue
            role = source.get("role")
            roles.add(role)
            if role not in {"authoritative_instruction", "state_owner", "evidence"}:
                issues.append(ValidationIssue("INVALID_SOURCE_ROLE", f"Unsupported role: {role}", f"$.authoritative_sources[{index}].role"))
        if "authoritative_instruction" not in roles:
            issues.append(ValidationIssue("NO_PROJECT_INSTRUCTION", "One authoritative_instruction is required", "$.authoritative_sources"))
    commands = contract.get("commands")
    if not _mapping(commands) or not isinstance(commands.get("full_verify"), list):
        issues.append(ValidationIssue("MISSING_FULL_VERIFY", "commands.full_verify list is required", "$.commands.full_verify"))
    rules = contract.get("path_rules")
    if not _mapping(rules) or "**" not in rules:
        issues.append(ValidationIssue("MISSING_DEFAULT_PATH_RULE", "path_rules must contain **", "$.path_rules"))
    else:
        for pattern, rule in rules.items():
            if not _mapping(rule):
                issues.append(ValidationIssue("INVALID_PATH_RULE", f"Rule {pattern} must be object", f"$.path_rules.{pattern}"))
                continue
            if rule.get("class") not in _PATH_CLASSES:
                issues.append(ValidationIssue("INVALID_PATH_CLASS", f"Unsupported class for {pattern}", f"$.path_rules.{pattern}.class"))
            if rule.get("approval") not in _APPROVALS:
                issues.append(ValidationIssue("INVALID_APPROVAL", f"Unsupported approval for {pattern}", f"$.path_rules.{pattern}.approval"))
    impact = contract.get("change_impact_rules")
    if not _mapping(impact):
        issues.append(ValidationIssue("MISSING_IMPACT_RULES", "change_impact_rules required", "$.change_impact_rules"))
    else:
        for key in ("public_api_change", "data_schema_change", "result_semantics_change"):
            if impact.get(key) not in _APPROVALS:
                issues.append(ValidationIssue("INVALID_IMPACT_RULE", f"{key} must be USER or AI", f"$.change_impact_rules.{key}"))
    caps = contract.get("capabilities")
    if not _mapping(caps):
        issues.append(ValidationIssue("MISSING_CAPABILITIES", "capabilities required", "$.capabilities"))
    else:
        if not _mapping(caps.get("network")) or not isinstance(caps["network"].get("default"), bool):
            issues.append(ValidationIssue("INVALID_NETWORK_POLICY", "network.default bool required", "$.capabilities.network"))
        if not _mapping(caps.get("secrets")) or not isinstance(caps["secrets"].get("default"), list):
            issues.append(ValidationIssue("INVALID_SECRET_POLICY", "secrets.default list required", "$.capabilities.secrets"))
        if not _mapping(caps.get("commands")) or not isinstance(caps["commands"].get("allow"), list):
            issues.append(ValidationIssue("INVALID_COMMAND_POLICY", "commands.allow list required", "$.capabilities.commands"))
        if not _mapping(caps.get("dependencies")) or caps["dependencies"].get("install") not in {"locked_only", "none"}:
            issues.append(ValidationIssue("INVALID_DEPENDENCY_POLICY", "dependencies.install invalid", "$.capabilities.dependencies"))
    env = contract.get("environment")
    if not _mapping(env):
        issues.append(ValidationIssue("MISSING_ENVIRONMENT", "environment required", "$.environment"))
    else:
        if env.get("home_access") is not False:
            issues.append(ValidationIssue("HOME_ACCESS_MUST_BE_FALSE", "HOME access must be denied", "$.environment.home_access"))
        for key in ("max_cpu", "max_memory_mb", "max_disk_mb", "timeout_minutes"):
            if not isinstance(env.get(key), int) or env[key] <= 0:
                issues.append(ValidationIssue("INVALID_RESOURCE_LIMIT", f"environment.{key} must be positive", f"$.environment.{key}"))
    for key in ("artifacts", "rollback", "owners"):
        if not _mapping(contract.get(key)):
            issues.append(ValidationIssue("MISSING_SECTION", f"{key} required", f"$.{key}"))
    return ValidationResult(ValidationStatus.INVALID if issues else ValidationStatus.VALID, issues, contract)


def validate_task_contract(contract: dict[str, Any]) -> ValidationResult:
    issues: list[ValidationIssue] = []
    if contract.get("schema_version") != "executor-task/1.0":
        issues.append(ValidationIssue("INVALID_SCHEMA_VERSION", "schema_version must be executor-task/1.0", "$.schema_version"))
    if not str(contract.get("id", "")).strip():
        issues.append(ValidationIssue("MISSING_TASK_ID", "Task id required", "$.id"))
    if contract.get("risk_class") not in {"LOW_RISK", "MEDIUM_RISK", "HIGH_RISK"}:
        issues.append(ValidationIssue("INVALID_RISK_CLASS", "Unsupported risk class", "$.risk_class"))
    if contract.get("mode") not in {"PLAN", "BUILD_AND_TEST", "AUDIT"}:
        issues.append(ValidationIssue("INVALID_MODE", "Unsupported mode", "$.mode"))
    for key in ("repositories", "test_contract", "capabilities", "budgets", "decision_policy", "merge_policy"):
        if not _mapping(contract.get(key)):
            issues.append(ValidationIssue("MISSING_SECTION", f"{key} required", f"$.{key}"))
    if _mapping(contract.get("decision_policy")) and contract["decision_policy"].get("max_decision_rounds") != 1:
        issues.append(ValidationIssue("DECISION_ROUND_LIMIT", "max_decision_rounds must equal 1", "$.decision_policy.max_decision_rounds"))
    if _mapping(contract.get("merge_policy")) and contract["merge_policy"].get("mode") != "PR_ONLY":
        issues.append(ValidationIssue("AUTO_MERGE_FORBIDDEN", "M0/M1 require PR_ONLY", "$.merge_policy.mode"))
    return ValidationResult(ValidationStatus.INVALID if issues else ValidationStatus.VALID, issues, contract)
