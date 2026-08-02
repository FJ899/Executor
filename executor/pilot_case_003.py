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


class PilotCase003WorkerError(PilotWorkerError):
    pass


CASE_003_CONTRACT = PilotCase001Contract(
    task_id="CASE-003",
    repository="litrgratis-pixel/executor-pilot-target",
    input_commit="c42bead2bbbff9c84486f17637ec80f35eeffa25",
    contract_blob_sha="0ae70e9f9a79e5e815f3d566ca5784059f461a9e",
    allowed_path="project_registry/registry.py",
    branch_prefix="executor/case-003",
    purpose="PILOT_CASE_003",
    commit_message="Fix CASE-003 canonical project ordering",
    container_label="case-003",
)

_BROKEN_TO_PAYLOAD = '''\
    def to_payload(self) -> dict[str, list[dict[str, str]]]:
        ordered = [project.to_mapping() for project in self._projects.values()]
        return {"projects": ordered}
'''

_FIXED_TO_PAYLOAD = '''\
    def to_payload(self) -> dict[str, list[dict[str, str]]]:
        ordered = [
            self._projects[project_id].to_mapping()
            for project_id in sorted(self._projects)
        ]
        return {"projects": ordered}
'''


def apply_case_003_worker(
    worktree: str | Path,
    *,
    contract: PilotCase001Contract = CASE_003_CONTRACT,
) -> None:
    replace_exact_source(
        worktree,
        contract=contract,
        broken=_BROKEN_TO_PAYLOAD,
        fixed=_FIXED_TO_PAYLOAD,
        defect_name="CASE-003",
        error_type=PilotCase003WorkerError,
    )


def verify_case_003_output_checkout(
    root_value: str | Path,
    *,
    output_commit: str,
    contract: PilotCase001Contract = CASE_003_CONTRACT,
) -> Path:
    return verify_output_checkout(
        root_value,
        output_commit=output_commit,
        contract=contract,
    )


def case_003_sandbox_spec(image: str) -> SandboxSpec:
    return pilot_sandbox_spec(image, contract=CASE_003_CONTRACT)


class PilotCase003DockerSandboxBackend(PinnedPilotDockerSandboxBackend):
    """Compatibility wrapper for the pinned CASE-003 sandbox boundary."""

    def __init__(
        self,
        *,
        policy_snapshot,
        contract: PilotCase001Contract = CASE_003_CONTRACT,
        docker_binary: str = "docker",
    ) -> None:
        super().__init__(
            policy_snapshot=policy_snapshot,
            contract=contract,
            docker_binary=docker_binary,
        )


def execute_case_003(
    *,
    repository_root: str | Path,
    runs_root: str | Path,
    sandbox_backend,
    sandbox_spec: SandboxSpec,
    contract: PilotCase001Contract = CASE_003_CONTRACT,
) -> dict[str, object]:
    def worker(worktree: Path, active_contract: PinnedPilotContract) -> None:
        apply_case_003_worker(worktree, contract=active_contract)

    return execute_pinned_task(
        repository_root=repository_root,
        runs_root=runs_root,
        sandbox_backend=sandbox_backend,
        sandbox_spec=sandbox_spec,
        contract=contract,
        worker=worker,
    )
