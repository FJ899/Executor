from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from executor.action_authorization import (
    AuthorizationContext,
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
from executor.repository_snapshot import RepositorySnapshotError, verify_source_tree
from executor.sandbox.docker import (
    DockerSandboxBackend,
    SandboxExecutionError,
    SandboxUnavailable,
)
from executor.sandbox.spec import CommandRule, SandboxExecutionContext, SandboxResult, SandboxSpec


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
    output = _git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout
    paths: set[str] = set()
    for line in output.splitlines():
        if len(line) < 4:
            raise GP001RuntimeError(f"unexpected Git status record: {line!r}")
        raw = line[3:].rsplit(" -> ", 1)[-1]
        paths.add(canonical_repository_path(raw))
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

    def __init__(self, *, policy_snapshot, task: dict[str, Any], docker_binary: str = "docker"):
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
    """First vertical runtime: contract -> fail -> authorized mutation -> verify -> report."""

    def __init__(
        self,
        *,
        task_path: str | Path,
        runs_root: str | Path,
        sandbox_backend,
        sandbox_spec: SandboxSpec,
    ) -> None:
        self.task_path = Path(task_path).resolve(strict=True)
        self.task = load_contract(self.task_path)
        validation = validate_gp001_task_contract(self.task)
        if validation.status != ValidationStatus.VALID:
            raise GP001Blocked(f"invalid GP001 task: {validation.to_dict()}")

        root = self.task_path.parent.parent
        test_path = (root / canonical_repository_path(self.task["test_contract"]["path"])).resolve(strict=True)
        test_path.relative_to(root)
        self.task_sha256 = _sha256(self.task_path.read_bytes())
        self.test_sha256 = _file_sha256(test_path)
        if self.test_sha256 != self.task["test_contract"]["sha256"].lower():
            raise GP001Blocked("locked GP001 test contract hash mismatch")

        self.repository = self.task["repositories"]["target"]["name"]
        self.input_commit = self.task["repositories"]["target"]["commit"]
        self.allowed = tuple(
            canonical_repository_path(p)
            for p in self.task["golden_path"]["scope"]["allowed_paths"]
        )
        if len(self.allowed) != 1:
            raise GP001Blocked("first GP001 runtime requires exactly one writable path")
        self.protected = tuple(
            validate_scope_pattern(p)
            for p in self.task["golden_path"]["scope"]["protected_paths"]
        )
        commands = self.task["golden_path"]["commands"]
        self.target_command = list(commands["target_test_argv"])
        self.regression_commands = [list(v) for v in commands["regression_argv"]]
        self.runs_root = Path(runs_root).expanduser().resolve(strict=False)
        self.backend = sandbox_backend
        self.spec = sandbox_spec
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

    def _authorize(
        self,
        packet: dict[str, Any],
        context: AuthorizationContext,
        mutation: AuthorizedFileMutation,
        now: datetime | None,
    ) -> dict[str, Any]:
        mutation.validate()
        expected_repo = {self.repository: self.input_commit}
        checks = (
            (context.task_id == self.task["id"], "task_id"),
            (context.risk_class == self.task["risk_class"], "risk_class"),
            (context.mode == self.task["mode"], "mode"),
            (context.repository_commits == expected_repo, "repository_commits"),
            (tuple(context.allowed_paths) == self.allowed, "allowed_paths"),
            (context.task_contract_sha256.lower() == self.task_sha256, "task_contract_sha256"),
            (context.test_contract_sha256.lower() == self.test_sha256, "test_contract_sha256"),
            (not context.external_projects, "external_projects"),
            (not context.auto_merge, "auto_merge"),
            (not context.default_network, "default_network"),
            (not context.default_secrets, "default_secrets"),
            (mutation.canonical_path() == self.allowed[0], "mutation_path"),
        )
        failed = [name for ok, name in checks if not ok]
        if failed:
            raise GP001Blocked(f"AAP context does not match GP001 contract: {failed}")

        result, decision = validate_action_authorization_packet(
            packet,
            context=context,
            now=now,
            consumed_packet_ids=self._consumed_packet_ids,
        )
        if result.status != ValidationStatus.VALID or decision is None:
            raise GP001Blocked(f"mutation authorization rejected: {result.to_dict()}")
        action, issuer = packet["action"], packet["issuer"]
        if decision.action_kind != "WRITE_REPOSITORY" or issuer.get("role") != "USER":
            raise GP001Blocked("GP001 mutation requires verified USER WRITE_REPOSITORY authorization")
        if action.get("paths") != [mutation.canonical_path()]:
            raise GP001Blocked("AAP does not bind the exact mutation path")
        if action.get("argv") != mutation.authorization_argv():
            raise GP001Blocked("AAP does not bind the exact mutation before/after hashes")
        if action.get("network") is not False or action.get("secrets") != []:
            raise GP001Blocked("AAP mutation may not request network or secrets")
        self._consumed_packet_ids.add(decision.packet_id)
        return {
            "packet_id": decision.packet_id,
            "payload_sha256": decision.payload_sha256,
            "issuer_role": decision.issuer_role,
            "issuer_id": decision.issuer_id,
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
        authorization_packet: dict[str, Any],
        authorization_context: AuthorizationContext,
        mutation: AuthorizedFileMutation,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        started = time.monotonic()
        run_dir = self.runs_root / authorization_context.run_id
        report: dict[str, Any] = {
            "schema_version": "executor-gp001-runtime-result/1.0",
            "task_id": self.task["id"],
            "run_id": authorization_context.run_id,
            "repository": self.repository,
            "input_commit": self.input_commit,
            "status": "FAILED",
            "error": None,
            "authorization": None,
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
                raise GP001Blocked(
                    f"run directory already exists: {authorization_context.run_id}"
                ) from exc

            pre = self._run(root, run_dir, self.target_command, "GP001_PRECHANGE", "pre-target")
            report["commands"].append(_result_payload(pre))
            if pre.timed_out or not pre.cleanup_verified:
                raise GP001RuntimeError("pre-change target execution is not trustworthy")
            if pre.exit_code == 0:
                raise GP001Blocked("target test does not fail on pinned input")
            report["evidence"]["pre_change_target_test"] = "FAIL"

            report["authorization"] = self._authorize(
                authorization_packet, authorization_context, mutation, now
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
