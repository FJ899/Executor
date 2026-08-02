from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Protocol, Sequence

from executor.source_acquisition import (
    CommandResult,
    ControlledGit,
    ControlledHttpsSourceAcquirer,
    ObjectIdentityError,
    SourceAcquisitionError,
    SourceAcquisitionRequest,
    SourceAcquisitionResult,
    build_manifest,
    load_source_acquisition_result,
    sha256_file,
    verify_manifest_unchanged,
)
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


class GitClient(Protocol):
    def run(self, git_args: Sequence[str]) -> CommandResult:
        ...


# Compatibility symbols retained for the stacked case modules. Host Git is
# intentionally unavailable on the pilot runtime path.
def git_command(root: Path, *args: str):
    del root, args
    raise PilotPolicyError(
        "host Git is forbidden for the pinned pilot; use ControlledGit"
    )


def git_stdout(root: Path, *args: str) -> str:
    del root, args
    raise PilotPolicyError(
        "host Git is forbidden for the pinned pilot; use ControlledGit"
    )


def _run_git(git: GitClient, *args: str) -> CommandResult:
    try:
        return git.run(args)
    except SourceAcquisitionError as exc:
        raise PilotTaskError(str(exc)) from exc


def _git_stdout(git: GitClient, *args: str) -> str:
    return _run_git(git, *args).stdout.strip()


def changed_paths(
    git: GitClient,
    root: Path,
    base: str,
    head: str = "HEAD",
) -> tuple[str, ...]:
    return tuple(
        line
        for line in _git_stdout(
            git,
            "-C",
            str(root),
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--name-only",
            f"{base}..{head}",
        ).splitlines()
        if line
    )


def verify_contract_blob(
    git: GitClient,
    root: Path,
    contract: PinnedPilotContract,
) -> None:
    blob = _git_stdout(
        git,
        "-C",
        str(root),
        "rev-parse",
        f"{contract.input_commit}:PILOT_CONTRACT.md",
    )
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


def _result_run_dir(root: Path) -> Path:
    resolved = root.resolve(strict=True)
    if resolved.name != "worktree":
        raise PilotPolicyError("pilot output must use the controlled worktree path")
    run_dir = resolved.parent
    try:
        load_source_acquisition_result(run_dir)
    except SourceAcquisitionError as exc:
        raise PilotPolicyError(str(exc)) from exc
    return run_dir


def verify_output_checkout(
    root_value: str | Path,
    *,
    output_commit: str,
    contract: PinnedPilotContract,
) -> Path:
    try:
        root = Path(root_value).resolve(strict=True)
        acquisition = load_source_acquisition_result(_result_run_dir(root))
        git = ControlledGit(acquisition)
    except (OSError, SourceAcquisitionError, PilotPolicyError) as exc:
        if isinstance(exc, PilotPolicyError):
            raise
        raise PilotPolicyError(str(exc)) from exc

    if acquisition.repository != contract.repository:
        raise PilotPolicyError("controlled source repository mismatch")
    if acquisition.commit != contract.input_commit:
        raise PilotPolicyError("controlled source commit mismatch")
    if acquisition.contract_blob != contract.contract_blob_sha:
        raise PilotPolicyError("controlled source contract blob mismatch")

    verify_contract_blob(git, root, contract)
    if _git_stdout(
        git,
        "-C",
        str(root),
        "status",
        "--porcelain",
        "--untracked-files=all",
    ):
        raise PilotPolicyError(f"{contract.task_id} output worktree is not clean")
    observed_head = _git_stdout(git, "-C", str(root), "rev-parse", "HEAD")
    if observed_head != output_commit:
        raise PilotPolicyError(
            f"{contract.task_id} output HEAD mismatch: expected {output_commit}"
        )
    commit_line = _git_stdout(
        git,
        "-C",
        str(root),
        "rev-list",
        "--parents",
        "-n",
        "1",
        output_commit,
    ).split()
    if len(commit_line) != 2 or commit_line[1] != contract.input_commit:
        raise PilotPolicyError(
            f"{contract.task_id} output must be one commit directly on pinned input"
        )
    changed = changed_paths(git, root, contract.input_commit, output_commit)
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
    """Narrow external-project exception for one exact controlled pilot task."""

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
        return root


def _acquisition_report(result: SourceAcquisitionResult) -> dict[str, object]:
    return {
        "input_model": result.input_model,
        "repository": result.repository,
        "canonical_url": result.canonical_url,
        "commit": result.commit,
        "root_tree": result.root_tree,
        "contract_path": result.contract_path,
        "contract_blob": result.contract_blob,
        "evidence_path": str(result.evidence_path),
        "evidence_sha256": sha256_file(result.evidence_path),
        "manifest_path": str(result.manifest_path),
        "manifest_sha256": sha256_file(result.manifest_path),
        "toolchain_image": result.toolchain_image,
        "toolchain_platform": result.toolchain_platform,
        "git_binary": result.git_binary,
        "git_version": result.git_version,
    }


def execute_pinned_task(
    *,
    repository_root: str | Path | None,
    runs_root: str | Path,
    sandbox_backend,
    sandbox_spec: SandboxSpec,
    contract: PinnedPilotContract,
    worker: Worker,
) -> dict[str, object]:
    run_id = uuid.uuid4().hex
    run_dir = Path(runs_root).expanduser().resolve(strict=False) / run_id
    worktree = run_dir / "worktree"
    branch = f"{contract.branch_prefix}-{run_id[:12]}"
    report: dict[str, object] = {
        "schema_version": "executor-pilot-result/2.0",
        "task_id": contract.task_id,
        "run_id": run_id,
        "repository": contract.repository,
        "input_commit": contract.input_commit,
        "input_root_tree": None,
        "contract_blob": contract.contract_blob_sha,
        "source_acquisition": None,
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

    if repository_root not in (None, ""):
        report.update(
            status="POLICY_BLOCKED",
            error="local repository_root input is unsupported by CONTROLLED_HTTPS_FETCH_V1",
        )
        return report

    try:
        acquirer = ControlledHttpsSourceAcquirer(
            docker_binary=getattr(sandbox_backend, "docker_binary", "docker")
        )
        acquisition = acquirer.acquire(
            SourceAcquisitionRequest(
                run_id=run_id,
                repository=contract.repository,
                commit=contract.input_commit,
                contract_blob=contract.contract_blob_sha,
                runs_root=Path(runs_root),
            )
        )
        run_dir = acquisition.run_dir
        worktree = run_dir / "worktree"
        git = ControlledGit(
            acquisition,
            docker_binary=getattr(sandbox_backend, "docker_binary", "docker"),
        )
        verify_contract_blob(git, acquisition.source_dir, contract)
        verify_manifest_unchanged(acquisition)
        report.update(
            input_root_tree=acquisition.root_tree,
            source_acquisition=_acquisition_report(acquisition),
            worktree=str(worktree),
        )

        _run_git(
            git,
            "--git-dir",
            str(acquisition.git_dir),
            "worktree",
            "add",
            "--detach",
            str(worktree),
            contract.input_commit,
        )
        _run_git(git, "-C", str(worktree), "switch", "-c", branch)
        worker(worktree, contract)
        pending = tuple(
            line
            for line in _git_stdout(
                git,
                "-C",
                str(worktree),
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

        _run_git(git, "-C", str(worktree), "add", "--", contract.allowed_path)
        _run_git(
            git,
            "-C",
            str(worktree),
            "commit",
            "-m",
            contract.resolved_commit_message(),
        )
        output_commit = _git_stdout(git, "-C", str(worktree), "rev-parse", "HEAD")
        verify_output_checkout(
            worktree,
            output_commit=output_commit,
            contract=contract,
        )
        changed = changed_paths(git, worktree, contract.input_commit, output_commit)
        diff_path = run_dir / "change.patch"
        diff_path.write_text(
            _run_git(
                git,
                "-C",
                str(worktree),
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

        verify_manifest_unchanged(acquisition)
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
                verify_manifest_unchanged(acquisition)
                write_report(run_dir, report)
                return report

        verify_manifest_unchanged(acquisition)
        report.update(
            commands=command_results,
            status="ACTION_COMPLETED_REVIEW_REQUIRED",
        )
        write_report(run_dir, report)
        return report
    except PilotPolicyError as exc:
        report.update(status="POLICY_BLOCKED", error=str(exc))
    except (
        ObjectIdentityError,
        SourceAcquisitionError,
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
