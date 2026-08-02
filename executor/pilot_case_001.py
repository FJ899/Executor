from __future__ import annotations

from pathlib import Path

from executor.pilot_core import (
    COMPILE_COMMAND,
    TEST_COMMAND,
    PinnedPilotContract,
    PilotPolicyError,
    PilotTaskError,
    PilotWorkerError,
    changed_paths,
    execute_pinned_task,
    git_command,
    git_stdout,
    pilot_sandbox_spec,
    replace_exact_source,
    result_dict,
    verify_contract_blob,
    verify_output_checkout,
    write_report,
)
from executor.sandbox.spec import SandboxSpec


PilotCase001Error = PilotTaskError
PilotCase001PolicyError = PilotPolicyError
PilotCase001Contract = PinnedPilotContract


class PilotCase001WorkerError(PilotWorkerError):
    pass


CASE_001_CONTRACT = PilotCase001Contract(
    task_id="CASE-001",
    repository="litrgratis-pixel/executor-pilot-target",
    input_commit="3934a94a5eebf750079200589d6dc40e024d44a0",
    contract_blob_sha="0ae70e9f9a79e5e815f3d566ca5784059f461a9e",
    allowed_path="project_registry/registry.py",
    branch_prefix="executor/case-001",
    purpose="PILOT_CASE_001",
    commit_message="Fix CASE-001 atomic batch insertion",
    container_label="case-001",
)

_BROKEN_ADD_MANY = '''\
    def add_many(self, projects: Iterable[Project]) -> None:
        """Add projects one by one, leaving earlier writes after a late duplicate."""

        for project in projects:
            if project.project_id in self._projects:
                raise DuplicateProjectError(
                    f"duplicate project_id: {project.project_id}"
                )
            self._projects[project.project_id] = project
'''

_FIXED_ADD_MANY = '''\
    def add_many(self, projects: Iterable[Project]) -> None:
        """Add a batch atomically; any duplicate leaves the registry unchanged."""

        batch = list(projects)
        seen = set(self._projects)
        for project in batch:
            if project.project_id in seen:
                raise DuplicateProjectError(
                    f"duplicate project_id: {project.project_id}"
                )
            seen.add(project.project_id)

        updated = dict(self._projects)
        updated.update((project.project_id, project) for project in batch)
        self._projects = updated
'''

# Compatibility aliases retained while the stacked pilot PRs are reviewed.
_git = git_command
_git_stdout = git_stdout
_changed_paths = changed_paths
_verify_contract_blob = verify_contract_blob
_result_dict = result_dict
_write_report = write_report


def apply_case_001_worker(
    worktree: str | Path,
    *,
    contract: PilotCase001Contract = CASE_001_CONTRACT,
) -> None:
    replace_exact_source(
        worktree,
        contract=contract,
        broken=_BROKEN_ADD_MANY,
        fixed=_FIXED_ADD_MANY,
        defect_name="CASE-001",
        error_type=PilotCase001WorkerError,
    )


def verify_case_001_output_checkout(
    root_value: str | Path,
    *,
    output_commit: str,
    contract: PilotCase001Contract = CASE_001_CONTRACT,
) -> Path:
    return verify_output_checkout(
        root_value,
        output_commit=output_commit,
        contract=contract,
    )


def case_001_sandbox_spec(image: str) -> SandboxSpec:
    return pilot_sandbox_spec(image, contract=CASE_001_CONTRACT)


def execute_case_001(
    *,
    repository_root: str | Path,
    runs_root: str | Path,
    sandbox_backend,
    sandbox_spec: SandboxSpec,
    contract: PilotCase001Contract = CASE_001_CONTRACT,
) -> dict[str, object]:
    def worker(worktree: Path, active_contract: PinnedPilotContract) -> None:
        apply_case_001_worker(worktree, contract=active_contract)

    return execute_pinned_task(
        repository_root=repository_root,
        runs_root=runs_root,
        sandbox_backend=sandbox_backend,
        sandbox_spec=sandbox_spec,
        contract=contract,
        worker=worker,
    )
