from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from executor.action_authorization import (
    AuthorizationContext,
    packet_payload_sha256,
    validate_action_authorization_packet,
)
from executor.contracts import ValidationStatus, load_contract
from executor.gp001_contract import validate_gp001_task_contract
from executor.repository_access import (
    RepositoryPathError,
    canonical_repository_path,
    validate_scope_pattern,
)
from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import (
    RepositorySnapshotError,
    verify_source_tree,
    verify_worktree_file,
)
from executor.sandbox.docker import (
    DockerSandboxBackend,
    SandboxExecutionError,
    SandboxUnavailable,
)
from executor.sandbox.policy_snapshot import (
    ExecutionPolicyError,
    ExecutionPolicySnapshot,
    load_execution_policy_snapshot,
)
from executor.sandbox.spec import CommandRule, SandboxExecutionContext, SandboxResult, SandboxSpec


_CANONICAL_TASK_PATH = "tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml"
_PROJECT_CONTRACT_PATH = "project_contracts/executor-self.yaml"
_POLICY_ISSUER_ID = "executor-policy"
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class GP001RuntimeError(RuntimeError):
    pass


class GP001Blocked(GP001RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorizedFileMutation:
    path: str
    expected_before_sha256: str
    replacement_text: str
    expected_after_sha256: str

    def canonical_path(self) -> str:
        try:
            return canonical_repository_path(self.path)
        except RepositoryPathError as exc:
            raise GP001Blocked(str(exc)) from exc

    def authorization_argv(self) -> list[str]:
        return [
            "gp001-file-replacement-v1",
            self.canonical_path(),
            self.expected_before_sha256,
            self.expected_after_sha256,
        ]

    def validate(self) -> None:
        for label, value in (
            ("expected_before_sha256", self.expected_before_sha256),
            ("expected_after_sha256", self.expected_after_sha256),
        ):
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise GP001Blocked(f"{label} must be lowercase SHA-256")
        if _sha256(self.replacement_text.encode("utf-8")) != self.expected_after_sha256:
            raise GP001Blocked("replacement payload does not match authorized after hash")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL="/dev/null",
        GIT_ATTR_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
    )
    try:
        result = subprocess.run(
            [
                "git", "-C", str(root),
                "-c", "core.hooksPath=/dev/null",
                "-c", "core.fsmonitor=false",
                "-c", "core.attributesFile=/dev/null",
                *args,
            ],
            stdin=subprocess.DEVNULL,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GP001RuntimeError(f"controlled Git failed to start: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise GP001RuntimeError(f"controlled Git {' '.join(args)} failed: {detail}")
    return result


def _changed_paths(root: Path) -> tuple[str, ...]:
    output = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout
    records = output.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        if not record:
            index += 1
            continue
        if len(record) < 4:
            raise GP001RuntimeError(f"unexpected Git status record: {record!r}")
        status = record[:2]
        path = record[3:]
        if "R" in status or "C" in status:
            index += 1
            if index >= len(records) or not records[index]:
                raise GP001RuntimeError("incomplete Git rename/copy status record")
            path = records[index]
        paths.add(canonical_repository_path(path))
        index += 1
    return tuple(sorted(paths))


def _result_payload(result: SandboxResult) -> dict[str, Any]:
    return {
        "argv": list(result.argv),
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timed_out": result.timed_out,
        "cleanup_verified": result.cleanup_verified,
        "execution_id": result.execution_id,
        "policy_sha256": result.policy_sha256,
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def build_gp001_sandbox_spec(task: dict[str, Any], image: str) -> SandboxSpec:
    validation = validate_gp001_task_contract(task)
    if validation.status != ValidationStatus.VALID:
        raise GP001Blocked(f"invalid GP001 task: {validation.to_dict()}")
    commands = task["golden_path"]["commands"]
    all_commands = [commands["target_test_argv"], *commands["regression_argv"]]
    return SandboxSpec(
        image=image,
        command_rules=tuple(
            CommandRule(argv[0], tuple(argv[1:])) for argv in all_commands
        ),
        timeout_seconds=min(int(task["budgets"]["max_wall_time_minutes"]) * 60, 300),
        network=False,
        secrets=(),
        home_access=False,
        labels={"creative-os-executor-gp001": "first-vertical-runtime-slice"},
    )


class GP001DockerSandboxBackend(DockerSandboxBackend):
    """Exact GP001 exception; global external-project execution stays disabled."""

    def __init__(self, *, policy_snapshot: ExecutionPolicySnapshot, task: dict[str, Any], docker_binary: str = "docker"):
        super().__init__(policy_snapshot=policy_snapshot, docker_binary=docker_binary)
        if validate_gp001_task_contract(task).status != ValidationStatus.VALID:
            raise SandboxExecutionError("GP001 sandbox requires a valid task contract")
        self.repository = task["repositories"]["target"]["name"]
        self.input_commit = task["repositories"]["target"]["commit"]
        self.allowed = tuple(
            canonical_repository_path(p)
            for p in task["golden_path"]["scope"]["allowed_paths"]
        )
        self.protected = tuple(
            validate_scope_pattern(p)
            for p in task["golden_path"]["scope"]["protected_paths"]
        )

    def authorize(self, context: SandboxExecutionContext) -> Path:
        policy = self._authoritative_policy()
        if policy.external_projects or policy.auto_merge:
            raise SandboxExecutionError("GP001 requires global external execution and auto-merge disabled")
        if policy.default_network or policy.default_secrets:
            raise SandboxExecutionError("GP001 requires network=false and no secrets")
        if context.purpose not in {"GP001_PRECHANGE", "GP001_POSTCHANGE"}:
            raise SandboxExecutionError(f"unsupported GP001 purpose: {context.purpose}")
        if context.repository != self.repository or context.commit != self.input_commit:
            raise SandboxExecutionError("GP001 repository binding mismatch")
        try:
            root = verify_repository_checkout(
                context.repository_root,
                repository=self.repository,
                commit=self.input_commit,
                require_head=True,
            )
        except RepositoryIdentityError as exc:
            raise SandboxExecutionError(f"unverified GP001 checkout: {exc}") from exc
        if Path(context.source_dir).resolve(strict=True) != root:
            raise SandboxExecutionError("GP001 sandbox source must be the verified checkout root")

        changed = _changed_paths(root)
        if context.purpose == "GP001_PRECHANGE":
            if changed:
                raise SandboxExecutionError(f"pre-change checkout is dirty: {list(changed)}")
            try:
                verify_source_tree(root, commit=self.input_commit, source_dir=root)
            except RepositorySnapshotError as exc:
                raise SandboxExecutionError(f"pre-change checkout mismatch: {exc}") from exc
        else:
            if changed != self.allowed:
                raise SandboxExecutionError(f"post-change scope mismatch: {list(changed)}")
            if any(fnmatch(path, pattern) for path in changed for pattern in self.protected):
                raise SandboxExecutionError("protected material changed")
        return root

    def build_create_command(self, **kwargs) -> list[str]:
        command = super().build_create_command(**kwargs)
        spec = kwargs["spec"]
        command[command.index("--workdir") + 1] = spec.source_mount
        image_index = command.index(spec.image)
        command[image_index:image_index] = [
            "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--env", f"PYTHONPYCACHEPREFIX={spec.workspace_mount}/pycache",
        ]
        return command


class GP001Runtime:
    """First vertical runtime: canonical contract -> fail -> authorized mutation -> verify -> report."""

    def __init__(
        self,
        *,
        executor_root: str | Path,
        executor_commit: str,
        runs_root: str | Path,
        image: str,
        docker_binary: str = "docker",
    ) -> None:
        try:
            snapshot = load_execution_policy_snapshot(executor_root, commit=executor_commit)
            root = snapshot.repository_root
            task_bytes = verify_worktree_file(root, commit=executor_commit, path=_CANONICAL_TASK_PATH)
            task_path = root / _CANONICAL_TASK_PATH
            task = load_contract(task_path)
            validation = validate_gp001_task_contract(task)
            if validation.status != ValidationStatus.VALID:
                raise GP001Blocked(f"invalid canonical GP001 task: {validation.to_dict()}")
            test_relative = canonical_repository_path(task["test_contract"]["path"])
            test_bytes = verify_worktree_file(root, commit=executor_commit, path=test_relative)
            project_bytes = verify_worktree_file(root, commit=executor_commit, path=_PROJECT_CONTRACT_PATH)
        except (
            ExecutionPolicyError,
            RepositorySnapshotError,
            RepositoryPathError,
            OSError,
        ) as exc:
            raise GP001Blocked(f"cannot load authoritative GP001 runtime inputs: {exc}") from exc

        self.policy_snapshot = snapshot
        self.task_path = task_path
        self.task = task
        self.task_sha256 = _sha256(task_bytes)
        self.test_sha256 = _sha256(test_bytes)
        self.project_contract_sha256 = _sha256(project_bytes)
        if self.test_sha256 != task["test_contract"]["sha256"].lower():
            raise GP001Blocked("locked GP001 test contract hash mismatch")

        self.repository = task["repositories"]["target"]["name"]
        self.input_commit = task["repositories"]["target"]["commit"]
        self.allowed = tuple(
            canonical_repository_path(p)
            for p in task["golden_path"]["scope"]["allowed_paths"]
        )
        if len(self.allowed) != 1:
            raise GP001Blocked("first GP001 runtime requires exactly one writable path")
        self.protected = tuple(
            validate_scope_pattern(p)
            for p in task["golden_path"]["scope"]["protected_paths"]
        )
        commands = task["golden_path"]["commands"]
        self.target_command = list(commands["target_test_argv"])
        self.regression_commands = [list(v) for v in commands["regression_argv"]]
        self.runs_root = Path(runs_root).expanduser().resolve(strict=False)
        self.spec = build_gp001_sandbox_spec(task, image)
        self.backend = GP001DockerSandboxBackend(
            policy_snapshot=snapshot,
            task=task,
            docker_binary=docker_binary,
        )
        self._consumed_packet_ids: set[str] = set()

    def _verify_clean_input(self, workspace: str | Path) -> Path:
        try:
            root = verify_repository_checkout(
                workspace,
                repository=self.repository,
                commit=self.input_commit,
                require_head=True,
            )
            if _changed_paths(root):
                raise GP001Blocked("GP001 workspace must start clean")
            verify_source_tree(root, commit=self.input_commit, source_dir=root)
            return root
        except (RepositoryIdentityError, RepositorySnapshotError, GP001RuntimeError) as exc:
            if isinstance(exc, GP001Blocked):
                raise
            raise GP001Blocked(f"input identity verification failed: {exc}") from exc

    def _authorization_context(self, run_id: str) -> AuthorizationContext:
        evidence_ref = f"policy-snapshot:{self.policy_snapshot.source_sha256}"
        return AuthorizationContext(
            run_id=run_id,
            task_id=self.task["id"],
            risk_class=self.task["risk_class"],
            mode=self.task["mode"],
            executor_commit=self.policy_snapshot.commit,
            policy_sha256=self.policy_snapshot.source_sha256,
            project_contract_sha256=self.project_contract_sha256,
            task_contract_sha256=self.task_sha256,
            test_contract_sha256=self.test_sha256,
            repository_commits={self.repository: self.input_commit},
            allowed_paths=self.allowed,
            external_projects=self.policy_snapshot.external_projects,
            auto_merge=self.policy_snapshot.auto_merge,
            default_network=self.policy_snapshot.default_network,
            default_secrets=self.policy_snapshot.default_secrets,
            verified_issuer_evidence={
                evidence_ref: ("POLICY_VERIFIER", _POLICY_ISSUER_ID),
            },
        )

    def _authorize(
        self,
        *,
        run_id: str,
        mutation: AuthorizedFileMutation,
        now: datetime | None,
    ) -> dict[str, Any]:
        mutation.validate()
        if mutation.canonical_path() != self.allowed[0]:
            raise GP001Blocked("mutation path is outside the frozen GP001 contract")
        if self.policy_snapshot.external_projects or self.policy_snapshot.auto_merge:
            raise GP001Blocked("GP001 canonical policy must keep external execution and auto-merge disabled")
        if self.policy_snapshot.default_network or self.policy_snapshot.default_secrets:
            raise GP001Blocked("GP001 canonical policy must keep network and secrets disabled")

        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        context = self._authorization_context(run_id)
        evidence_ref = next(iter(context.verified_issuer_evidence))
        packet_id = f"gp001-{run_id}-{mutation.expected_after_sha256[:16]}"
        if len(packet_id) > 128:
            packet_id = f"gp001-{_sha256(packet_id.encode())[:48]}"
        issued_at = current.replace(microsecond=0)
        expires_at = issued_at + timedelta(minutes=10)
        packet = {
            "schema_version": "executor-action-authorization/1.0",
            "packet_id": packet_id,
            "run_id": run_id,
            "issued_at": issued_at.isoformat().replace("+00:00", "Z"),
            "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            "issuer": {
                "role": "POLICY_VERIFIER",
                "id": _POLICY_ISSUER_ID,
                "evidence_ref": evidence_ref,
            },
            "bindings": {
                "task_id": context.task_id,
                "risk_class": context.risk_class,
                "mode": context.mode,
                "executor_commit": context.executor_commit,
                "policy_sha256": context.policy_sha256,
                "project_contract_sha256": context.project_contract_sha256,
                "task_contract_sha256": context.task_contract_sha256,
                "test_contract_sha256": context.test_contract_sha256,
                "repository_commits": context.repository_commits,
            },
            "action": {
                "kind": "WRITE_REPOSITORY",
                "argv": mutation.authorization_argv(),
                "paths": [mutation.canonical_path()],
                "network": False,
                "secrets": [],
                "external_project": False,
            },
            "decision": {
                "status": "AUTHORIZED",
                "reasons": [
                    "Mutation stays inside the canonical user-approved GP001 task contract",
                    "Mutation is bound to exact before/after file hashes",
                ],
            },
            "constraints": {
                "max_uses": 1,
                "max_duration_seconds": 600,
                "manual_confirmation_required": False,
            },
            "integrity": {"algorithm": "SHA-256", "payload_sha256": ""},
        }
        packet["integrity"]["payload_sha256"] = packet_payload_sha256(packet)
        result, decision = validate_action_authorization_packet(
            packet,
            context=context,
            now=current,
            consumed_packet_ids=self._consumed_packet_ids,
        )
        if result.status != ValidationStatus.VALID or decision is None:
            raise GP001Blocked(f"policy authorization rejected: {result.to_dict()}")
        if decision.action_kind != "WRITE_REPOSITORY" or decision.issuer_role != "POLICY_VERIFIER":
            raise GP001Blocked("GP001 requires POLICY_VERIFIER WRITE_REPOSITORY authorization")
        self._consumed_packet_ids.add(decision.packet_id)
        return {
            "packet_id": decision.packet_id,
            "payload_sha256": decision.payload_sha256,
            "issuer_role": decision.issuer_role,
            "issuer_id": decision.issuer_id,
            "issuer_evidence_ref": decision.issuer_evidence_ref,
            "action_argv": mutation.authorization_argv(),
        }

    def _run(self, root: Path, run_dir: Path, argv: list[str], purpose: str, label: str) -> SandboxResult:
        return self.backend.run(
            spec=self.spec,
            context=SandboxExecutionContext(
                repository=self.repository,
                commit=self.input_commit,
                repository_root=root,
                source_dir=root,
                purpose=purpose,
            ),
            output_dir=run_dir / label,
            argv=argv,
        )

    def _mutate(self, root: Path, mutation: AuthorizedFileMutation) -> None:
        path = mutation.canonical_path()
        if path != self.allowed[0] or any(fnmatch(path, p) for p in self.protected):
            raise GP001Blocked("mutation path is not writable under GP001 contract")
        target = root / path
        meta = target.lstat()
        if target.is_symlink() or not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1:
            raise GP001Blocked("mutation target must be one regular non-linked file")
        if _file_sha256(target) != mutation.expected_before_sha256:
            raise GP001Blocked("authorized before-hash does not match workspace")
        tmp = target.with_name(f".{target.name}.gp001-{uuid.uuid4().hex}")
        try:
            tmp.write_bytes(mutation.replacement_text.encode("utf-8"))
            os.chmod(tmp, stat.S_IMODE(meta.st_mode))
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        if _file_sha256(target) != mutation.expected_after_sha256:
            raise GP001RuntimeError("authorized after-hash does not match mutation result")
        if _changed_paths(root) != (path,):
            raise GP001RuntimeError("mutation changed more than the authorized file")

    def execute(
        self,
        *,
        workspace: str | Path,
        mutation: AuthorizedFileMutation,
        run_id: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        actual_run_id = run_id or f"gp001-{uuid.uuid4().hex}"
        if _RUN_ID.fullmatch(actual_run_id) is None:
            raise GP001Blocked("run_id contains unsupported characters")
        run_dir = self.runs_root / actual_run_id
        report: dict[str, Any] = {
            "schema_version": "executor-gp001-runtime-result/1.0",
            "task_id": self.task["id"],
            "run_id": actual_run_id,
            "repository": self.repository,
            "input_commit": self.input_commit,
            "status": "FAILED",
            "error": None,
            "authorization": None,
            "authorization_model": "CANONICAL_USER_APPROVED_TASK_PLUS_POLICY_VERIFIER_ACTION_GATE",
            "authorization_consumption": "RUN_LOCAL_REPLAY_GUARD_ONLY",
            "changed_paths": [],
            "diff_path": None,
            "commands": [],
            "evidence": {
                "input_identity": "UNKNOWN",
                "pre_change_target_test": "UNKNOWN",
                "post_change_target_test": "UNKNOWN",
                "regression_checks": "UNKNOWN",
                "diff_scope": "UNKNOWN",
                "protected_material": "UNKNOWN",
                "execution_limits": "UNKNOWN",
                "result_artifact": "UNKNOWN",
            },
            "human_decision_required": True,
        }
        try:
            root = self._verify_clean_input(workspace)
            report["evidence"]["input_identity"] = "MATCH"
            try:
                self.runs_root.relative_to(root)
            except ValueError:
                pass
            else:
                raise GP001Blocked("runs_root must be outside the GP001 workspace")
            self.runs_root.mkdir(parents=True, exist_ok=True)
            try:
                run_dir.mkdir(mode=0o700)
            except FileExistsError as exc:
                raise GP001Blocked(f"run directory already exists: {actual_run_id}") from exc

            pre = self._run(root, run_dir, self.target_command, "GP001_PRECHANGE", "pre-target")
            report["commands"].append(_result_payload(pre))
            if pre.timed_out or not pre.cleanup_verified:
                raise GP001RuntimeError("pre-change target execution is not trustworthy")
            if pre.exit_code == 0:
                raise GP001Blocked("target test does not fail on pinned input")
            report["evidence"]["pre_change_target_test"] = "FAIL"

            report["authorization"] = self._authorize(
                run_id=actual_run_id,
                mutation=mutation,
                now=now,
            )
            self._mutate(root, mutation)

            post = self._run(root, run_dir, self.target_command, "GP001_POSTCHANGE", "post-target")
            report["commands"].append(_result_payload(post))
            if not post.ok:
                raise GP001RuntimeError("target test did not pass after mutation")
            report["evidence"]["post_change_target_test"] = "PASS"

            for index, argv in enumerate(self.regression_commands, 1):
                result = self._run(root, run_dir, argv, "GP001_POSTCHANGE", f"regression-{index}")
                report["commands"].append(_result_payload(result))
                if not result.ok:
                    raise GP001RuntimeError(f"regression command {index} failed")
            report["evidence"]["regression_checks"] = "PASS"

            changed = _changed_paths(root)
            if changed != self.allowed:
                raise GP001RuntimeError(f"final diff scope mismatch: {list(changed)}")
            report["changed_paths"] = list(changed)
            report["evidence"]["diff_scope"] = "ALLOWED"
            if any(fnmatch(path, p) for path in changed for p in self.protected):
                raise GP001RuntimeError("protected material appears in diff")
            report["evidence"]["protected_material"] = "UNCHANGED"

            patch = _git(root, "diff", "--no-ext-diff", "--no-textconv", "--binary", self.input_commit).stdout
            patch_lines = len(patch.splitlines())
            if patch_lines > int(self.task["budgets"]["max_patch_lines"]):
                raise GP001Blocked("final patch exceeds max_patch_lines")
            diff_path = run_dir / "change.patch"
            diff_path.write_text(patch, encoding="utf-8")
            report["diff_path"] = str(diff_path)

            if time.monotonic() - started > int(self.task["budgets"]["max_wall_time_minutes"]) * 60:
                raise GP001RuntimeError("GP001 wall-time budget exceeded")
            report["evidence"]["execution_limits"] = "RESPECTED"
            report["status"] = "ACTION_COMPLETED_REVIEW_REQUIRED"
        except GP001Blocked as exc:
            report["status"], report["error"] = "BLOCKED", str(exc)
        except (
            GP001RuntimeError,
            SandboxUnavailable,
            SandboxExecutionError,
            OSError,
            ValueError,
        ) as exc:
            report["status"], report["error"] = "FAILED", str(exc)

        if run_dir.exists():
            report["evidence"]["result_artifact"] = "PRESENT"
            _write_report(run_dir / "report.json", report)
        return report
