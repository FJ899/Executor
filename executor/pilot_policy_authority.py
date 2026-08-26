from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from executor.contracts import ValidationStatus, load_contract
from executor.gp001_contract import validate_gp001_task_contract
from executor.repository_snapshot import RepositorySnapshotError, verify_worktree_file
from executor.sandbox.policy_snapshot import ExecutionPolicySnapshot


_CANONICAL_GP001_TASK_PATH = "tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml"


@dataclass(frozen=True)
class EffectivePilotPolicyAuthority:
    authority_class: str
    max_production_files: int
    bounded_external_repositories: tuple[str, ...]
    controlled_fixture_task_id: str | None = None


def _common_policy_is_bounded(policy: ExecutionPolicySnapshot) -> bool:
    return (
        policy.external_projects is False
        and policy.auto_merge is False
        and policy.default_network is False
        and not policy.default_secrets
    )


def _canonical_gp001_derivation_matches(
    canonical: dict[str, Any],
    contract: dict[str, Any],
) -> bool:
    try:
        golden = canonical["golden_path"]
        problem = golden["problem"]
        scope = golden["scope"]
        commands = golden["commands"]
        budgets = canonical["budgets"]
        frozen_task = contract["task"]
    except (KeyError, TypeError):
        return False

    expected = {
        "problem_statement": problem.get("statement"),
        "allowed_paths": scope.get("allowed_paths"),
        "protected_paths": scope.get("protected_paths"),
        "precondition_argv": [commands.get("target_test_argv")],
        "postcondition_argv": [commands.get("target_test_argv")],
        "regression_argv": commands.get("regression_argv"),
        "max_patch_lines": budgets.get("max_patch_lines"),
    }
    for field, value in expected.items():
        if frozen_task.get(field) != value:
            return False
    allowed = frozen_task.get("allowed_paths")
    maximum = frozen_task.get("max_production_files")
    if not isinstance(allowed, list) or type(maximum) is not int:
        return False
    if maximum != len(allowed) or not 1 <= maximum <= 3:
        return False

    boundary = contract.get("authority_boundary")
    if not isinstance(boundary, dict):
        return False
    if (
        boundary.get("effect") != "BOUNDED_DRAFT_PR_ONLY"
        or boundary.get("merge") is not False
        or boundary.get("deploy") is not False
        or boundary.get("release") is not False
    ):
        return False
    return True


def resolve_pilot_policy_authority(
    policy: ExecutionPolicySnapshot,
    *,
    contract: dict[str, Any],
    executor_commit: str,
) -> EffectivePilotPolicyAuthority | None:
    """Resolve only authority already present in the verified Executor policy.

    Generic bounded-pilot repositories preserve their historical/current behavior.
    The canonical GP001 controlled fixture is admitted only when the frozen product
    contract is byte-bound to the exact canonical GP001 task and that exact
    task/repository/commit triple is already authorized by controlled fixture policy.
    """

    if not _common_policy_is_bounded(policy):
        return None

    target = contract.get("target")
    if not isinstance(target, dict):
        return None
    repository = target.get("repository")
    commit = target.get("commit")
    if not isinstance(repository, str) or not isinstance(commit, str):
        return None

    profile = policy.bounded_pilot_profile(repository=repository)
    if profile is not None:
        if not profile.draft_pr_only:
            return None
        return EffectivePilotPolicyAuthority(
            authority_class="BOUNDED_PILOT_REPOSITORY",
            max_production_files=profile.max_production_files,
            bounded_external_repositories=tuple(
                item.repository for item in policy.bounded_pilot_repositories
            ),
        )

    binding = contract.get("formation_binding")
    if not isinstance(binding, dict):
        return None
    canonical_sha = binding.get("canonical_task_sha256")
    if (
        not isinstance(canonical_sha, str)
        or len(canonical_sha) != 64
        or any(ch not in "0123456789abcdef" for ch in canonical_sha)
    ):
        return None

    try:
        canonical_bytes = verify_worktree_file(
            policy.repository_root,
            commit=executor_commit,
            path=_CANONICAL_GP001_TASK_PATH,
        )
        canonical = load_contract(policy.repository_root / _CANONICAL_GP001_TASK_PATH)
    except (RepositorySnapshotError, OSError, ValueError):
        return None
    if hashlib.sha256(canonical_bytes).hexdigest() != canonical_sha:
        return None
    if validate_gp001_task_contract(canonical).status != ValidationStatus.VALID:
        return None

    try:
        task_id = canonical["id"]
        canonical_target = canonical["repositories"]["target"]
    except (KeyError, TypeError):
        return None
    if (
        not isinstance(task_id, str)
        or canonical_target.get("name") != repository
        or canonical_target.get("commit") != commit
    ):
        return None
    if not policy.authorizes_controlled_external_fixture(
        task=task_id,
        repository=repository,
        commit=commit,
    ):
        return None
    if not _canonical_gp001_derivation_matches(canonical, contract):
        return None

    return EffectivePilotPolicyAuthority(
        authority_class="CONTROLLED_EXTERNAL_FIXTURE",
        max_production_files=contract["task"]["max_production_files"],
        bounded_external_repositories=(repository,),
        controlled_fixture_task_id=task_id,
    )


def revalidate_pilot_policy_authority(
    policy: ExecutionPolicySnapshot,
    *,
    authority: EffectivePilotPolicyAuthority,
    repository: str,
    commit: str,
) -> bool:
    if not _common_policy_is_bounded(policy):
        return False
    if authority.authority_class == "BOUNDED_PILOT_REPOSITORY":
        profile = policy.bounded_pilot_profile(repository=repository)
        return (
            profile is not None
            and profile.draft_pr_only
            and profile.max_production_files == authority.max_production_files
        )
    if authority.authority_class == "CONTROLLED_EXTERNAL_FIXTURE":
        task_id = authority.controlled_fixture_task_id
        return (
            isinstance(task_id, str)
            and authority.bounded_external_repositories == (repository,)
            and policy.authorizes_controlled_external_fixture(
                task=task_id,
                repository=repository,
                commit=commit,
            )
        )
    return False
