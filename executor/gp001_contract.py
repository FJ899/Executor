from __future__ import annotations

import argparse
import json
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from executor.contracts import (
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
    load_contract,
    validate_task_contract,
)
from executor.repository_access import (
    RepositoryPathError,
    canonical_repository_path,
    validate_scope_pattern,
)


_GP001_SCHEMA = "executor-golden-path-task/1.0"
_REQUIRED_SUCCESS = {
    "input_identity": "MATCH",
    "pre_change_target_test": "FAIL",
    "post_change_target_test": "PASS",
    "regression_checks": "PASS",
    "diff_scope": "ALLOWED",
    "protected_material": "UNCHANGED",
    "execution_limits": "RESPECTED",
    "result_artifact": "PRESENT",
}
_ALLOWED_TERMINAL_STATUSES = {
    "ACTION_COMPLETED_REVIEW_REQUIRED",
    "BLOCKED",
    "FAILED",
}


def _issue(issues: list[ValidationIssue], code: str, message: str, path: str) -> None:
    issues.append(ValidationIssue(code, message, path))


def _mapping(value: object) -> bool:
    return isinstance(value, dict)


def _argv(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item for item in value)
    )


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_gp001_task_contract(contract: dict[str, Any]) -> ValidationResult:
    """Validate the GP001 extension without changing the generic task schema.

    ``executor-task/1.0`` remains the base task contract. GP001 adds one
    machine-readable ``golden_path`` section whose semantics are validated here.
    The function is intentionally structural: repository identity and test
    evidence remain the responsibility of the authoritative bundle/verifier.
    """

    base = validate_task_contract(contract)
    issues = list(base.issues)

    if contract.get("mode") != "BUILD_AND_TEST":
        _issue(issues, "GP001_MODE_REQUIRED", "GP001 requires BUILD_AND_TEST mode", "$.mode")
    if contract.get("risk_class") != "LOW_RISK":
        _issue(issues, "GP001_RISK_CLASS_REQUIRED", "The first GP001 contract is LOW_RISK", "$.risk_class")

    repositories = contract.get("repositories")
    if not _mapping(repositories) or set(repositories) != {"target"}:
        _issue(
            issues,
            "GP001_SINGLE_TARGET_REQUIRED",
            "GP001 must bind exactly one target repository",
            "$.repositories",
        )

    capabilities = contract.get("capabilities")
    if _mapping(capabilities):
        if capabilities.get("network") is not False:
            _issue(issues, "GP001_NETWORK_FORBIDDEN", "GP001 must run without network access", "$.capabilities.network")
        if capabilities.get("secrets") != []:
            _issue(issues, "GP001_SECRETS_FORBIDDEN", "GP001 must not receive secrets", "$.capabilities.secrets")
        commands = capabilities.get("commands")
        if not isinstance(commands, list) or set(commands) != {"python", "git"}:
            _issue(
                issues,
                "GP001_COMMAND_CAPABILITIES",
                "GP001 command capabilities must be exactly python and git",
                "$.capabilities.commands",
            )

    budgets = contract.get("budgets")
    if _mapping(budgets):
        for key in ("max_model_calls", "max_execution_iterations", "max_wall_time_minutes", "max_patch_lines"):
            if not _positive_int(budgets.get(key)):
                _issue(issues, "GP001_BUDGET_REQUIRED", f"{key} must be a positive integer", f"$.budgets.{key}")

    golden_path = contract.get("golden_path")
    if not _mapping(golden_path):
        _issue(issues, "MISSING_GP001_CONTRACT", "golden_path object is required", "$.golden_path")
        return ValidationResult(ValidationStatus.INVALID, issues, contract)

    if golden_path.get("schema_version") != _GP001_SCHEMA:
        _issue(
            issues,
            "INVALID_GP001_SCHEMA",
            f"golden_path.schema_version must be {_GP001_SCHEMA}",
            "$.golden_path.schema_version",
        )
    if golden_path.get("kind") != "FIX_FAILING_TEST":
        _issue(issues, "INVALID_GP001_KIND", "GP001 kind must be FIX_FAILING_TEST", "$.golden_path.kind")

    problem = golden_path.get("problem")
    if not _mapping(problem):
        _issue(issues, "MISSING_GP001_PROBLEM", "golden_path.problem is required", "$.golden_path.problem")
        problem = {}
    target_test = str(problem.get("target_test", "")).strip()
    target_test_file = str(problem.get("target_test_file", "")).strip()
    if not str(problem.get("statement", "")).strip():
        _issue(issues, "MISSING_GP001_PROBLEM_STATEMENT", "Problem statement is required", "$.golden_path.problem.statement")
    if not target_test:
        _issue(issues, "MISSING_GP001_TARGET_TEST", "Target failing test is required", "$.golden_path.problem.target_test")
    if problem.get("expected_pre_change") != "FAIL":
        _issue(
            issues,
            "GP001_PRECONDITION_MUST_FAIL",
            "The pinned target test must be expected to fail before mutation",
            "$.golden_path.problem.expected_pre_change",
        )
    try:
        canonical_target_test_file = canonical_repository_path(target_test_file)
    except RepositoryPathError as exc:
        canonical_target_test_file = ""
        _issue(issues, "INVALID_GP001_TARGET_TEST_FILE", str(exc), "$.golden_path.problem.target_test_file")

    scope = golden_path.get("scope")
    allowed_paths: list[str] = []
    protected_patterns: list[str] = []
    if not _mapping(scope):
        _issue(issues, "MISSING_GP001_SCOPE", "golden_path.scope is required", "$.golden_path.scope")
        scope = {}
    raw_allowed = scope.get("allowed_paths")
    if not isinstance(raw_allowed, list) or not raw_allowed:
        _issue(issues, "MISSING_GP001_ALLOWED_PATH", "At least one allowed path is required", "$.golden_path.scope.allowed_paths")
    else:
        for index, value in enumerate(raw_allowed):
            try:
                canonical = canonical_repository_path(str(value))
            except RepositoryPathError as exc:
                _issue(issues, "INVALID_GP001_ALLOWED_PATH", str(exc), f"$.golden_path.scope.allowed_paths[{index}]")
                continue
            if any(token in canonical for token in ("*", "?", "[")):
                _issue(
                    issues,
                    "GP001_ALLOWED_PATH_MUST_BE_EXACT",
                    "The first GP001 slice uses exact allowed file paths, not globs",
                    f"$.golden_path.scope.allowed_paths[{index}]",
                )
                continue
            allowed_paths.append(canonical)

    raw_protected = scope.get("protected_paths")
    if not isinstance(raw_protected, list) or not raw_protected:
        _issue(issues, "MISSING_GP001_PROTECTED_PATH", "Protected paths are required", "$.golden_path.scope.protected_paths")
    else:
        for index, value in enumerate(raw_protected):
            try:
                protected_patterns.append(validate_scope_pattern(str(value)))
            except RepositoryPathError as exc:
                _issue(issues, "INVALID_GP001_PROTECTED_PATH", str(exc), f"$.golden_path.scope.protected_paths[{index}]")

    for allowed in allowed_paths:
        if any(fnmatch(allowed, pattern) for pattern in protected_patterns):
            _issue(
                issues,
                "GP001_SCOPE_OVERLAP",
                f"Allowed path is also protected: {allowed}",
                "$.golden_path.scope",
            )
    if canonical_target_test_file and not any(
        fnmatch(canonical_target_test_file, pattern) for pattern in protected_patterns
    ):
        _issue(
            issues,
            "GP001_TARGET_TEST_NOT_PROTECTED",
            "The target test file must be covered by protected_paths",
            "$.golden_path.problem.target_test_file",
        )
    if scope.get("scope_expansion") != "REPORT_ONLY_NEW_CONTRACT_REQUIRED":
        _issue(
            issues,
            "GP001_SCOPE_EXPANSION_FORBIDDEN",
            "Out-of-scope work may only be reported and requires a new contract",
            "$.golden_path.scope.scope_expansion",
        )

    authorization = golden_path.get("authorization")
    if not _mapping(authorization):
        _issue(issues, "MISSING_GP001_AUTHORIZATION", "Authorization boundary is required", "$.golden_path.authorization")
    else:
        if authorization.get("mutation_requires_authorization") is not True:
            _issue(
                issues,
                "GP001_MUTATION_REQUIRES_AUTHORIZATION",
                "Mutation must require authorization",
                "$.golden_path.authorization.mutation_requires_authorization",
            )
        if authorization.get("scope_expansion_requires_new_contract") is not True:
            _issue(
                issues,
                "GP001_SCOPE_REQUIRES_NEW_CONTRACT",
                "Scope expansion requires a new task contract",
                "$.golden_path.authorization.scope_expansion_requires_new_contract",
            )

    discovery = golden_path.get("discovery")
    if not _mapping(discovery):
        _issue(issues, "MISSING_GP001_DISCOVERY_POLICY", "Discovery policy is required", "$.golden_path.discovery")
    else:
        if discovery.get("out_of_scope_findings") != "REPORT_ONLY":
            _issue(
                issues,
                "GP001_DISCOVERY_REPORT_ONLY",
                "Out-of-scope findings must be report-only",
                "$.golden_path.discovery.out_of_scope_findings",
            )
        if discovery.get("may_expand_contract") is not False:
            _issue(
                issues,
                "GP001_DELIBERATION_CANNOT_EXPAND_CONTRACT",
                "Discovery/deliberation may not expand the contract",
                "$.golden_path.discovery.may_expand_contract",
            )

    commands = golden_path.get("commands")
    if not _mapping(commands):
        _issue(issues, "MISSING_GP001_COMMANDS", "Exact verification commands are required", "$.golden_path.commands")
    else:
        target_argv = commands.get("target_test_argv")
        if not _argv(target_argv):
            _issue(issues, "INVALID_GP001_TARGET_COMMAND", "target_test_argv must be a non-empty argv list", "$.golden_path.commands.target_test_argv")
        elif target_test and target_test not in target_argv:
            _issue(
                issues,
                "GP001_TARGET_COMMAND_MISMATCH",
                "The exact target test identifier must appear in target_test_argv",
                "$.golden_path.commands.target_test_argv",
            )
        regressions = commands.get("regression_argv")
        if not isinstance(regressions, list) or not regressions or not all(_argv(item) for item in regressions):
            _issue(
                issues,
                "INVALID_GP001_REGRESSION_COMMANDS",
                "regression_argv must contain at least one exact argv list",
                "$.golden_path.commands.regression_argv",
            )

    success = golden_path.get("success")
    if not _mapping(success):
        _issue(issues, "MISSING_GP001_SUCCESS", "Success observations are required", "$.golden_path.success")
    else:
        for key, expected in _REQUIRED_SUCCESS.items():
            if success.get(key) != expected:
                _issue(
                    issues,
                    "INVALID_GP001_SUCCESS_CRITERION",
                    f"{key} must equal {expected}",
                    f"$.golden_path.success.{key}",
                )

    result_policy = golden_path.get("result_policy")
    if not _mapping(result_policy):
        _issue(issues, "MISSING_GP001_RESULT_POLICY", "Result policy is required", "$.golden_path.result_policy")
    else:
        if result_policy.get("success_status") != "ACTION_COMPLETED_REVIEW_REQUIRED":
            _issue(
                issues,
                "GP001_SELF_ACCEPTANCE_FORBIDDEN",
                "A successful execution may only end at ACTION_COMPLETED_REVIEW_REQUIRED",
                "$.golden_path.result_policy.success_status",
            )
        statuses = result_policy.get("allowed_terminal_statuses")
        if not isinstance(statuses, list) or set(statuses) != _ALLOWED_TERMINAL_STATUSES:
            _issue(
                issues,
                "INVALID_GP001_TERMINAL_STATUSES",
                "GP001 terminal statuses are ACTION_COMPLETED_REVIEW_REQUIRED, BLOCKED and FAILED",
                "$.golden_path.result_policy.allowed_terminal_statuses",
            )

    status = ValidationStatus.INVALID if issues else ValidationStatus.VALID
    return ValidationResult(status, issues, contract)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m executor.gp001_contract")
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    result = validate_gp001_task_contract(load_contract(args.path))
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == ValidationStatus.VALID else 2


if __name__ == "__main__":
    raise SystemExit(main())
