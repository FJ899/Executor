from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, verify_source_tree
from executor.sandbox.docker import (
    DockerSandboxBackend,
    SandboxExecutionError,
    SandboxUnavailable,
)
from executor.sandbox.spec import (
    CommandRule,
    SandboxExecutionContext,
    SandboxResult,
    SandboxSpec,
)


class PilotTaskError(RuntimeError):
    pass


class PilotPolicyError(PilotTaskError):
    pass


class PilotWorkerError(PilotTaskError):
    pass


@dataclass(frozen=True)
class PinnedPilotContract:
    task_id: str
    repository: str
    input_commit: str
    contract_blob_sha: str
    allowed_path: str
    branch_prefix: str = "executor/case-001"
    purpose: str = "PILOT_CASE_001"
    commit_message: str | None = None
    container_label: str | None = None

    def resolved_commit_message(self) -> str:
        return self.commit_message or f"Fix {self.task_id} pinned pilot defect"

    def resolved_container_label(self) -> str:
        return self.container_label or self.task_id.lower()


COMPILE_COMMAND = ("python", "-m", "compileall", "-q", "project_registry", "tests")
TEST_COMMAND = ("python", "-m", "unittest", "discover", "-s", "tests", "-v")

Worker = Callable[[Path, PinnedPilotContract], None]


def git_command(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    environment.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
    )
    command = [
        "git",
        "-C",
        str(root),
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "core.autocrlf=false",
        "-c",
        "commit.gpgSign=false",
        *args,
    ]
    try:
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PilotTaskError(f"git command failed to start: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PilotTaskError(f"git {' '.join(args)} failed: {detail}")
    return result


def git_stdout(root: Path, *args: str) -> str:
    return git_command(root, *args).stdout.strip()


def changed_paths(root: Path, base: str, head: str = "HEAD") -> tuple[str, ...]:
    return tuple(
        line
        for line in git_stdout(
            root,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--name-only",
            f"{base}..{head}",
        ).splitlines()
        if line
    )


def verify_contract_blob(root: Path, contract: PinnedPilotContract) -> None:
    blob = git_stdout(root, "rev-parse", f"{contract.input_commit}:PILOT_CONTRACT.md")
    if blob != contract.contract_blob_sha:
        raise PilotPolicyError("pinned PILOT_CONTRACT.md blob mismatch")


def replace_exact_source(
    worktree: str | Path,
    *,
    contract: PinnedPilotContract,
    broken: str,
    fixed: str,
    defect_name: str,
    error_type: type[PilotWorkerError] = PilotWorkerError,
) -> None:
    path = Path(worktree) / contract.allowed_path
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise error_type(f"cannot read worker target: {exc}") from exc
    if source.count(broken) != 1:
        raise error_type(f"pinned {defect_name} defect was not found exactly once")
    try:
        path.write_text(source.replace(broken, fixed), encoding="utf-8")
    except OSError as exc:
        raise error_type(f"cannot write worker target: {exc}") from exc


def verify_output_checkout(
    root_value: str | Path,
    *,
    output_commit: str,
    contract: PinnedPilotContract,
) -> Path:
    try:
        root = verify_repository_checkout(
            root_value,
            repository=contract.repository,
            commit=output_commit,
            require_head=True,
        )
    except RepositoryIdentityError as exc:
        raise PilotPolicyError(str(exc)) from exc
    verify_contract_blob(root, contract)
    if git_stdout(root, "status", "--porcelain", "--untracked-files=all"):
        raise PilotPolicyError(f"{contract.task_id} output worktree is not clean")
    commit_line = git_stdout(
        root, "rev-list", "--parents", "-n", "1", output_commit
    ).split()
    if len(commit_line) != 2 or commit_line[1] != contract.input_commit:
        raise PilotPolicyError(
            f"{contract.task_id} output must be one commit directly on pinned input"
        )
    changed = changed_paths(root, contract.input_commit, output_commit)
    if changed != (contract.allowed_path,):
        raise PilotPolicyError(
            f"{contract.task_id} changed paths are not allowed: {list(changed)}"
        )
    return root


def pilot_sandbox_spec(image: str, *, contract: PinnedPilotContract) -> SandboxSpec:
    return SandboxSpec(
        image=image,
        command_rules=(
            CommandRule(COMPILE_COMMAND[0], COMPILE_COMMAND[1:]),
            CommandRule(TEST_COMMAND[0], TEST_COMMAND[1:]),
        ),
        max_cpu=1.0,
        max_memory_mb=256,
        max_disk_mb=32,
        timeout_seconds=30,
        pids_limit=64,
        network=False,
        secrets=(),
        home_access=False,
        labels={
            "creative-os-executor-pilot": contract.resolved_container_label(),
        },
    )


def result_dict(result: SandboxResult) -> dict[str, object]:
    return {
        "argv": list(result.argv),
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
        "duration_seconds": result.duration_seconds,
        "cleanup_verified": result.cleanup_verified,
        "execution_id": result.execution_id,
        "policy_sha256": result.policy_sha256,
    }


def write_report(run_dir: Path, report: dict[str, object]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


class PinnedPilotDockerSandboxBackend(DockerSandboxBackend):
    """Narrow external-project exception for one exact pinned pilot task."""

    def __init__(
        self,
        *,
        policy_snapshot,
        contract: PinnedPilotContract,
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
                f"{self.contract.task_id} pilot requires global external project execution to remain disabled"
            )
        if policy.auto_merge:
            raise SandboxExecutionError(f"{self.contract.task_id} pilot forbids auto merge")
        if policy.default_network or policy.default_secrets:
            raise SandboxExecutionError(
                f"{self.contract.task_id} pilot requires network=false and no default secrets"
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
            root = verify_output_checkout(
                context.repository_root,
                output_commit=context.commit,
                contract=self.contract,
            )
        except PilotPolicyError as exc:
            raise SandboxExecutionError(
                f"Unverified {self.contract.task_id} output: {exc}"
            ) from exc

        try:
            source = Path(context.source_dir).resolve(strict=True)
        except OSError as exc:
            raise SandboxExecutionError(
                f"{self.contract.task_id} source cannot be resolved: {exc}"
            ) from exc
        if source != root:
            raise SandboxExecutionError(
                f"{self.contract.task_id} sandbox must mount the verified output repository root"
            )
        try:
            verify_source_tree(root, commit=context.commit, source_dir=root)
        except RepositorySnapshotError as exc:
            raise SandboxExecutionError(
                f"{self.contract.task_id} source does not match the output commit: {exc}"
            ) from exc
        return root


def execute_pinned_task(
    *,
    repository_root: str | Path,
    runs_root: str | Path,
    sandbox_backend,
    sandbox_spec: SandboxSpec,
    contract: PinnedPilotContract,
    worker: Worker,
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
            raise PilotPolicyError(str(exc)) from exc
        verify_contract_blob(source_root, contract)
        if git_stdout(
            source_root, "status", "--porcelain", "--untracked-files=all"
        ):
            raise PilotPolicyError("source checkout must be clean")

        run_dir.mkdir(parents=True, exist_ok=False)
        git_command(
            source_root,
            "worktree",
            "add",
            "--detach",
            str(worktree),
            contract.input_commit,
        )
        git_command(worktree, "switch", "-c", branch)
        worker(worktree, contract)
        pending = tuple(
            line
            for line in git_stdout(
                worktree,
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--name-only",
            ).splitlines()
            if line
        )
        if pending != (contract.allowed_path,):
            raise PilotPolicyError(
                f"worker changed forbidden paths: {list(pending)}"
            )

        git_command(worktree, "add", "--", contract.allowed_path)
        git_command(
            worktree,
            "-c",
            "user.name=Creative OS Executor",
            "-c",
            "user.email=executor@local.invalid",
            "commit",
            "-m",
            contract.resolved_commit_message(),
        )
        output_commit = git_stdout(worktree, "rev-parse", "HEAD")
        verify_output_checkout(
            worktree,
            output_commit=output_commit,
            contract=contract,
        )
        changed = changed_paths(worktree, contract.input_commit, output_commit)
        diff_path = run_dir / "change.patch"
        diff_path.write_text(
            git_command(
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
            command_results.append(result_dict(result))
            if not result.ok:
                report.update(
                    commands=command_results,
                    status="TESTS_FAILED",
                    error=f"sandbox command failed: {' '.join(command)}",
                )
                write_report(run_dir, report)
                return report

        report.update(
            commands=command_results,
            status="ACTION_COMPLETED_REVIEW_REQUIRED",
        )
        write_report(run_dir, report)
        return report
    except PilotPolicyError as exc:
        report.update(status="POLICY_BLOCKED", error=str(exc))
    except (
        PilotWorkerError,
        PilotTaskError,
        SandboxUnavailable,
        SandboxExecutionError,
        OSError,
        ValueError,
    ) as exc:
        report.update(status="EXECUTION_FAILED", error=str(exc))

    write_report(run_dir, report)
    return report
