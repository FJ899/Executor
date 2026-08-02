from __future__ import annotations

from pathlib import Path

from executor.pilot_case_001 import PilotCase001Contract
from executor.pilot_core import (
    PinnedPilotContract,
    PinnedPilotDockerSandboxBackend,
    PilotWorkerError,
    execute_pinned_task,
    pilot_sandbox_spec,
    replace_exact_source,
    verify_output_checkout,
)
from executor.sandbox.spec import SandboxSpec


class PilotCase002WorkerError(PilotWorkerError):
    pass


CASE_002_CONTRACT = PilotCase001Contract(
    task_id="CASE-002",
    repository="litrgratis-pixel/executor-pilot-target",
    input_commit="c3683bf37ad6a3f1d49c0ca05ebdd41627e9a5be",
    contract_blob_sha="0ae70e9f9a79e5e815f3d566ca5784059f461a9e",
    allowed_path="project_registry/registry.py",
    branch_prefix="executor/case-002",
    purpose="PILOT_CASE_002",
    commit_message="Fix CASE-002 reopen authorization",
    container_label="case-002",
)

_BROKEN_TRANSITION = '''\
        reason = reopen_reason.strip() if reopen_reason else None

        changed = replace(
            project,
            status=target,
            reopen_reason=(reason if target is ProjectStatus.ACTIVE else None),
        )
'''

_FIXED_TRANSITION = '''\
        reason = reopen_reason.strip() if reopen_reason else None
        if (
            project.status is ProjectStatus.CLOSED
            and target is ProjectStatus.ACTIVE
            and not reason
        ):
            raise InvalidTransitionError(
                "CLOSED -> ACTIVE requires a non-empty reopen_reason"
            )

        changed = replace(
            project,
            status=target,
            reopen_reason=(reason if target is ProjectStatus.ACTIVE else None),
        )
'''


def apply_case_002_worker(
    worktree: str | Path,
    *,
    contract: PilotCase001Contract = CASE_002_CONTRACT,
) -> None:
    replace_exact_source(
        worktree,
        contract=contract,
        broken=_BROKEN_TRANSITION,
        fixed=_FIXED_TRANSITION,
        defect_name="CASE-002",
        error_type=PilotCase002WorkerError,
    )


def verify_case_002_output_checkout(
    root_value: str | Path,
    *,
    output_commit: str,
    contract: PilotCase001Contract = CASE_002_CONTRACT,
) -> Path:
    return verify_output_checkout(
        root_value,
        output_commit=output_commit,
        contract=contract,
    )


def case_002_sandbox_spec(image: str) -> SandboxSpec:
    return pilot_sandbox_spec(image, contract=CASE_002_CONTRACT)


class PilotCase002DockerSandboxBackend(PinnedPilotDockerSandboxBackend):
    """Compatibility wrapper for the pinned CASE-002 sandbox boundary."""

    def __init__(
        self,
        *,
        policy_snapshot,
        contract: PilotCase001Contract = CASE_002_CONTRACT,
        docker_binary: str = "docker",
    ) -> None:
        super().__init__(
            policy_snapshot=policy_snapshot,
            contract=contract,
            docker_binary=docker_binary,
        )


def execute_case_002(
    *,
    repository_root: str | Path,
    runs_root: str | Path,
    sandbox_backend,
    sandbox_spec: SandboxSpec,
    contract: PilotCase001Contract = CASE_002_CONTRACT,
) -> dict[str, object]:
    def worker(worktree: Path, active_contract: PinnedPilotContract) -> None:
        apply_case_002_worker(worktree, contract=active_contract)

    return execute_pinned_task(
        repository_root=repository_root,
        runs_root=runs_root,
        sandbox_backend=sandbox_backend,
        sandbox_spec=sandbox_spec,
        contract=contract,
        worker=worker,
    )
