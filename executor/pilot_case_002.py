from __future__ import annotations

import json
import uuid
from dataclasses import replace
from pathlib import Path

from executor.pilot_case_001 import (
    COMPILE_COMMAND,
    TEST_COMMAND,
    PilotCase001Contract,
    PilotCase001Error,
    PilotCase001PolicyError,
    _changed_paths,
    _git,
    _git_stdout,
    _result_dict,
    _verify_contract_blob,
    _write_report,
    case_001_sandbox_spec,
)
from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, verify_source_tree
from executor.sandbox.docker import (
    DockerSandboxBackend,
    SandboxExecutionError,
    SandboxUnavailable,
)
from executor.sandbox.spec import SandboxExecutionContext, SandboxSpec


class PilotCase002WorkerError(PilotCase001Error):
    pass


CASE_002_CONTRACT = PilotCase001Contract(
    task_id="CASE-002",
    repository="litrgratis-pixel/executor-pilot-target",
    input_commit="c3683bf37ad6a3f1d49c0ca05ebdd41627e9a5be",
    contract_blob_sha="0ae70e9f9a79e5e815f3d566ca5784059f461a9e",
    allowed_path="project_registry/registry.py",
    branch_prefix="executor/case-002",
    purpose="PILOT_CASE_002",
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
    path = Path(worktree) / contract.allowed_path
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PilotCase002WorkerError(f"cannot read worker target: {exc}") from exc
    if source.count(_BROKEN_TRANSITION) != 1:
        raise PilotCase002WorkerError(
            "pinned CASE-002 defect was not found exactly once"
        )
    try:
        path.write_text(
            source.replace(_BROKEN_TRANSITION, _FIXED_TRANSITION),
            encoding="utf-8",
        )
    except OSError as exc:
        raise PilotCase002WorkerError(f"cannot write worker target: {exc}") from exc


def verify_case_002_output_checkout(
    root_value: str | Path,
    *,
    output_commit: str,
    contract: PilotCase001Contract = CASE_002_CONTRACT,
) -> Path:
    try:
        root = verify_repository_checkout(
            root_value,
            repository=contract.repository,
            commit=output_commit,
            require_head=True,
        )
    except RepositoryIdentityError as exc:
        raise PilotCase001PolicyError(str(exc)) from exc
    _verify_contract_blob(root, contract)
    if _git_stdout(root, "status", "--porcelain", "--untracked-files=all"):
        raise PilotCase001PolicyError("CASE-002 output worktree is not clean")
    commit_line = _git_stdout(
        root, "rev-list", "--parents", "-n", "1", output_commit
    ).split()
    if len(commit_line) != 2 or commit_line[1] != contract.input_commit:
        raise PilotCase001PolicyError(
            "CASE-002 output must be one commit directly on pinned input"
        )
    changed = _changed_paths(root, contract.input_commit, output_commit)
    if changed != (contract.allowed_path,):
        raise PilotCase001PolicyError(
            f"CASE-002 changed paths are not allowed: {list(changed)}"
        )
    return root


def case_002_sandbox_spec(image: str) -> SandboxSpec:
    return replace(
        case_001_sandbox_spec(image),
        labels={"creative-os-executor-pilot": "case-002"},
    )


class PilotCase002DockerSandboxBackend(DockerSandboxBackend):
    """Narrow external-project exception for the pinned CASE-002 pilot only."""

    def __init__(
        self,
        *,
        policy_snapshot,
        contract: PilotCase001Contract = CASE_002_CONTRACT,
        docker_binary: str = "docker",
    ) -> None:
        super().__init__(
            policy_snapshot=policy_snapshot,
            docker_binary=docker_binary,
        )
        self.contract = contract

    def build_create_command(self, **kwargs) -> list[str]:
        command = super().build_create_command(**kwargs)
        workdir_index = command.index("--workdir") + 1
        command[workdir_index] = "/source"
        image = kwargs["spec"].image
        image_index = command.index(image)
        command[image_index:image_index] = [
            "--env",
            "PYTHONPYCACHEPREFIX=/workspace/pycache",
        ]
        return command

    def authorize(self, context: SandboxExecutionContext) -> Path:
        policy = self._authoritative_policy()
        if policy.external_projects:
            raise SandboxExecutionError(
                "CASE-002 pilot requires global external project execution to remain disabled"
            )
        if policy.auto_merge:
            raise SandboxExecutionError("CASE-002 pilot forbids auto merge")
        if policy.default_network or policy.default_secrets:
            raise SandboxExecutionError(
                "CASE-002 pilot requires network=false and no default secrets"
            )
        if context.purpose != self.contract.purpose:
            raise SandboxExecutionError(
                f"Unsupported pilot purpose: {context.purpose}"
            )
        if context.repository != self.contract.repository:
            raise SandboxExecutionError(
                f"Pilot repository is {context.repository}, expected {self.contract.repository}"
            )
        try:
            root = verify_case_002_output_checkout(
                context.repository_root,
                output_commit=context.commit,
                contract=self.contract,
            )
        except PilotCase001PolicyError as exc:
            raise SandboxExecutionError(
                f"Unverified CASE-002 output: {exc}"
            ) from exc

        try:
            source = Path(context.source_dir).resolve(strict=True)
        except OSError as exc:
            raise SandboxExecutionError(
                f"CASE-002 source cannot be resolved: {exc}"
            ) from exc
        if source != root:
            raise SandboxExecutionError(
                "CASE-002 sandbox must mount the verified output repository root"
            )
        try:
            verify_source_tree(root, commit=context.commit, source_dir=root)
        except RepositorySnapshotError as exc:
            raise SandboxExecutionError(
                f"CASE-002 source does not match the output commit: {exc}"
            ) from exc
        return root


def execute_case_002(
    *,
    repository_root: str | Path,
    runs_root: str | Path,
    sandbox_backend,
    sandbox_spec: SandboxSpec,
    contract: PilotCase001Contract = CASE_002_CONTRACT,
) -> dict[str, object]:
    run_id = uuid.uuid4().hex
    run_dir = Path(runs_root) / run_id
    worktree = run_dir / "worktree"
    branch = f"{contract.branch_prefix}-{run_id[:12]}"
    report: dict[str, object] = {
        "schema_version": "executor-pilot-result/1.0",
        "task_id": contract.task_id,
        "run_id": run_id,
        "repository": contract.repository,
        "input_commit": contract.input_commit,
        "output_commit": None,
        "branch": branch,
        "worktree": str(worktree),
        "changed_paths": [],
        "diff_path": None,
        "commands": [],
        "status": "EXECUTION_FAILED",
        "error": None,
        "human_decision_required": True,
    }

    try:
        source_candidate = Path(repository_root).resolve(strict=True)
        runs_base = Path(runs_root).resolve()
        try:
            runs_base.relative_to(source_candidate)
        except ValueError:
            pass
        else:
            report.update(
                status="POLICY_BLOCKED",
                error="runs_root must be outside source checkout",
            )
            return report

        try:
            source_root = verify_repository_checkout(
                source_candidate,
                repository=contract.repository,
                commit=contract.input_commit,
                require_head=True,
            )
        except RepositoryIdentityError as exc:
            raise PilotCase001PolicyError(str(exc)) from exc
        _verify_contract_blob(source_root, contract)
        if _git_stdout(
            source_root, "status", "--porcelain", "--untracked-files=all"
        ):
            raise PilotCase001PolicyError("source checkout must be clean")

        run_dir.mkdir(parents=True, exist_ok=False)
        _git(
            source_root,
            "worktree",
            "add",
            "--detach",
            str(worktree),
            contract.input_commit,
        )
        _git(worktree, "switch", "-c", branch)
        apply_case_002_worker(worktree, contract=contract)
        pending = tuple(
            line
            for line in _git_stdout(
                worktree,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--name-only",
            ).splitlines()
            if line
        )
        if pending != (contract.allowed_path,):
            raise PilotCase001PolicyError(
                f"worker changed forbidden paths: {list(pending)}"
            )

        _git(worktree, "add", "--", contract.allowed_path)
        _git(
            worktree,
            "-c",
            "user.name=Creative OS Executor",
            "-c",
            "user.email=executor@local.invalid",
            "commit",
            "-m",
            "Fix CASE-002 reopen authorization",
        )
        output_commit = _git_stdout(worktree, "rev-parse", "HEAD")
        verify_case_002_output_checkout(
            worktree,
            output_commit=output_commit,
            contract=contract,
        )
        changed = _changed_paths(worktree, contract.input_commit, output_commit)
        diff_path = run_dir / "change.patch"
        diff_path.write_text(
            _git(
                worktree,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--binary",
                contract.input_commit,
                output_commit,
            ).stdout,
            encoding="utf-8",
        )
        report.update(
            output_commit=output_commit,
            changed_paths=list(changed),
            diff_path=str(diff_path),
        )

        context = SandboxExecutionContext(
            repository=contract.repository,
            commit=output_commit,
            repository_root=worktree,
            source_dir=worktree,
            purpose=contract.purpose,
        )
        command_results = []
        for index, command in enumerate((COMPILE_COMMAND, TEST_COMMAND), start=1):
            result = sandbox_backend.run(
                spec=sandbox_spec,
                context=context,
                output_dir=run_dir / f"sandbox-{index}",
                argv=list(command),
            )
            command_results.append(_result_dict(result))
            if not result.ok:
                report.update(
                    commands=command_results,
                    status="TESTS_FAILED",
                    error=f"sandbox command failed: {' '.join(command)}",
                )
                _write_report(run_dir, report)
                return report

        report.update(
            commands=command_results,
            status="ACTION_COMPLETED_REVIEW_REQUIRED",
        )
        _write_report(run_dir, report)
        return report
    except PilotCase001PolicyError as exc:
        report.update(status="POLICY_BLOCKED", error=str(exc))
    except (
        PilotCase002WorkerError,
        PilotCase001Error,
        SandboxUnavailable,
        SandboxExecutionError,
        OSError,
        ValueError,
    ) as exc:
        report.update(status="EXECUTION_FAILED", error=str(exc))

    _write_report(run_dir, report)
    return report
