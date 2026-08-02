from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.sandbox.docker import SandboxExecutionError, SandboxUnavailable
from executor.sandbox.spec import CommandRule, SandboxExecutionContext, SandboxResult, SandboxSpec


class PilotCase001Error(RuntimeError):
    pass


class PilotCase001PolicyError(PilotCase001Error):
    pass


class PilotCase001WorkerError(PilotCase001Error):
    pass


@dataclass(frozen=True)
class PilotCase001Contract:
    task_id: str
    repository: str
    input_commit: str
    contract_blob_sha: str
    allowed_path: str
    branch_prefix: str = "executor/case-001"
    purpose: str = "PILOT_CASE_001"


CASE_001_CONTRACT = PilotCase001Contract(
    task_id="CASE-001",
    repository="litrgratis-pixel/executor-pilot-target",
    input_commit="3934a94a5eebf750079200589d6dc40e024d44a0",
    contract_blob_sha="0ae70e9f9a79e5e815f3d566ca5784059f461a9e",
    allowed_path="project_registry/registry.py",
)

COMPILE_COMMAND = ("python", "-m", "compileall", "-q", "project_registry", "tests")
TEST_COMMAND = ("python", "-m", "unittest", "discover", "-s", "tests", "-v")

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


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
        raise PilotCase001Error(f"git command failed to start: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PilotCase001Error(f"git {' '.join(args)} failed: {detail}")
    return result


def _git_stdout(root: Path, *args: str) -> str:
    return _git(root, *args).stdout.strip()


def _changed_paths(root: Path, base: str, head: str = "HEAD") -> tuple[str, ...]:
    return tuple(
        line
        for line in _git_stdout(
            root,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--name-only",
            f"{base}..{head}",
        ).splitlines()
        if line
    )


def _verify_contract_blob(root: Path, contract: PilotCase001Contract) -> None:
    blob = _git_stdout(root, "rev-parse", f"{contract.input_commit}:PILOT_CONTRACT.md")
    if blob != contract.contract_blob_sha:
        raise PilotCase001PolicyError("pinned PILOT_CONTRACT.md blob mismatch")


def verify_case_001_output_checkout(
    root_value: str | Path,
    *,
    output_commit: str,
    contract: PilotCase001Contract = CASE_001_CONTRACT,
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
        raise PilotCase001PolicyError("CASE-001 output worktree is not clean")
    commit_line = _git_stdout(root, "rev-list", "--parents", "-n", "1", output_commit).split()
    if len(commit_line) != 2 or commit_line[1] != contract.input_commit:
        raise PilotCase001PolicyError("output must be one commit directly on pinned input")
    changed = _changed_paths(root, contract.input_commit, output_commit)
    if changed != (contract.allowed_path,):
        raise PilotCase001PolicyError(f"CASE-001 changed paths are not allowed: {list(changed)}")
    return root


def apply_case_001_worker(
    worktree: str | Path,
    *,
    contract: PilotCase001Contract = CASE_001_CONTRACT,
) -> None:
    path = Path(worktree) / contract.allowed_path
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PilotCase001WorkerError(f"cannot read worker target: {exc}") from exc
    if source.count(_BROKEN_ADD_MANY) != 1:
        raise PilotCase001WorkerError("pinned CASE-001 defect was not found exactly once")
    try:
        path.write_text(source.replace(_BROKEN_ADD_MANY, _FIXED_ADD_MANY), encoding="utf-8")
    except OSError as exc:
        raise PilotCase001WorkerError(f"cannot write worker target: {exc}") from exc


def case_001_sandbox_spec(image: str) -> SandboxSpec:
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
        labels={"creative-os-executor-pilot": "case-001"},
    )


def _result_dict(result: SandboxResult) -> dict[str, object]:
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


def _write_report(run_dir: Path, report: dict[str, object]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def execute_case_001(
    *,
    repository_root: str | Path,
    runs_root: str | Path,
    sandbox_backend,
    sandbox_spec: SandboxSpec,
    contract: PilotCase001Contract = CASE_001_CONTRACT,
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
            report.update(status="POLICY_BLOCKED", error="runs_root must be outside source checkout")
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
        if _git_stdout(source_root, "status", "--porcelain", "--untracked-files=all"):
            raise PilotCase001PolicyError("source checkout must be clean")

        run_dir.mkdir(parents=True, exist_ok=False)
        _git(source_root, "worktree", "add", "--detach", str(worktree), contract.input_commit)
        _git(worktree, "switch", "-c", branch)
        apply_case_001_worker(worktree, contract=contract)
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
            raise PilotCase001PolicyError(f"worker changed forbidden paths: {list(pending)}")

        _git(worktree, "add", "--", contract.allowed_path)
        _git(
            worktree,
            "-c", "user.name=Creative OS Executor",
            "-c", "user.email=executor@local.invalid",
            "commit", "-m", "Fix CASE-001 atomic batch insertion",
        )
        output_commit = _git_stdout(worktree, "rev-parse", "HEAD")
        verify_case_001_output_checkout(worktree, output_commit=output_commit, contract=contract)
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

        report.update(commands=command_results, status="ACTION_COMPLETED_REVIEW_REQUIRED")
        _write_report(run_dir, report)
        return report
    except PilotCase001PolicyError as exc:
        report.update(status="POLICY_BLOCKED", error=str(exc))
    except (
        PilotCase001WorkerError,
        PilotCase001Error,
        SandboxUnavailable,
        SandboxExecutionError,
        OSError,
        ValueError,
    ) as exc:
        report.update(status="EXECUTION_FAILED", error=str(exc))

    _write_report(run_dir, report)
    return report
