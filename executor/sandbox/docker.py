from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, verify_source_tree
from executor.sandbox.command_policy import validate_argv
from executor.sandbox.policy_snapshot import (
    ExecutionPolicyError,
    ExecutionPolicySnapshot,
    load_execution_policy_snapshot,
)
from executor.sandbox.spec import SandboxExecutionContext, SandboxResult, SandboxSpec


class SandboxUnavailable(RuntimeError):
    pass


class SandboxExecutionError(RuntimeError):
    pass


_IMAGE_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_CONTAINER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_EXECUTION_ID = re.compile(r"^[0-9a-f]{32}$")
_OWNER_LABEL = "creative-os-executor.execution-id"
_POLICY_LABEL = "creative-os-executor.policy-sha256"


class DockerSandboxBackend:
    def __init__(
        self,
        *,
        policy_snapshot: ExecutionPolicySnapshot,
        docker_binary: str = "docker",
        control_repository: str = "JTJ07/Executor",
    ):
        if not isinstance(policy_snapshot, ExecutionPolicySnapshot):
            raise SandboxExecutionError(
                "A verified ExecutionPolicySnapshot is required; raw policy dictionaries are forbidden"
            )
        self.policy_snapshot = policy_snapshot
        self.docker_binary = docker_binary
        self.control_repository = control_repository

    def _authoritative_policy(self) -> ExecutionPolicySnapshot:
        try:
            current = load_execution_policy_snapshot(
                self.policy_snapshot.repository_root,
                commit=self.policy_snapshot.commit,
                repository=self.policy_snapshot.repository,
            )
        except ExecutionPolicyError as exc:
            raise SandboxExecutionError(
                f"Executor policy snapshot is no longer authoritative: {exc}"
            ) from exc
        if current != self.policy_snapshot:
            raise SandboxExecutionError(
                "Executor policy snapshot does not match the verified policy file"
            )
        return current

    def preflight(self) -> None:
        binary = shutil.which(self.docker_binary)
        if binary is None:
            raise SandboxUnavailable(
                "Docker CLI is unavailable; host execution fallback is forbidden"
            )
        completed = subprocess.run(
            [binary, "version", "--format", "{{.Server.Version}}"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            raise SandboxUnavailable(
                f"Docker daemon is unavailable: {completed.stderr.strip()}"
            )

    def authorize(self, context: SandboxExecutionContext) -> Path:
        policy = self._authoritative_policy()
        if context.purpose not in {"EXECUTOR_FIXTURE", "PROJECT"}:
            raise SandboxExecutionError(
                f"Unsupported sandbox execution purpose: {context.purpose}"
            )
        if (
            context.purpose == "EXECUTOR_FIXTURE"
            and context.repository != self.control_repository
        ):
            raise SandboxExecutionError(
                "EXECUTOR_FIXTURE is restricted to the Executor control repository"
            )
        if not policy.external_projects and not (
            context.repository == self.control_repository
            and context.purpose == "EXECUTOR_FIXTURE"
        ):
            raise SandboxExecutionError(
                "External project execution is disabled by EXECUTOR_POLICY.yaml; "
                "only Executor fixtures are allowed"
            )
        if (
            context.repository == self.control_repository
            and context.purpose == "EXECUTOR_FIXTURE"
        ):
            try:
                context_root = Path(context.repository_root).resolve(strict=True)
                policy_root = policy.repository_root.resolve(strict=True)
            except OSError as exc:
                raise SandboxExecutionError(
                    f"Executor fixture repository cannot be resolved: {exc}"
                ) from exc
            if context_root != policy_root or context.commit != policy.commit:
                raise SandboxExecutionError(
                    "Executor fixture root and commit must match the bound policy snapshot"
                )

        try:
            repository_root = verify_repository_checkout(
                context.repository_root,
                repository=context.repository,
                commit=context.commit,
                require_head=True,
            )
        except RepositoryIdentityError as exc:
            raise SandboxExecutionError(
                f"Unverified sandbox repository context: {exc}"
            ) from exc

        source_input = Path(context.source_dir)
        source_candidate = (
            source_input if source_input.is_absolute() else repository_root / source_input
        )
        source_lexical = Path(os.path.abspath(source_candidate))
        try:
            lexical_relative = source_lexical.relative_to(repository_root)
        except ValueError as exc:
            raise SandboxExecutionError(
                "Sandbox source directory escapes the verified repository"
            ) from exc
        current = repository_root
        for part in lexical_relative.parts:
            current = current / part
            if current.is_symlink():
                raise SandboxExecutionError(
                    f"Sandbox source path contains a symlink component: {part}"
                )
        try:
            source = source_lexical.resolve(strict=True)
            source.relative_to(repository_root)
        except OSError as exc:
            raise SandboxExecutionError(
                f"Sandbox source directory cannot be resolved: {exc}"
            ) from exc
        except ValueError as exc:
            raise SandboxExecutionError(
                "Sandbox source directory escapes the verified repository"
            ) from exc
        if not source.is_dir():
            raise SandboxExecutionError(
                f"Sandbox source directory does not exist: {source}"
            )
        try:
            verify_source_tree(
                repository_root,
                commit=context.commit,
                source_dir=source,
            )
        except RepositorySnapshotError as exc:
            raise SandboxExecutionError(
                f"Sandbox source does not match the locked commit: {exc}"
            ) from exc
        return source

    @staticmethod
    def _validate_image(image: str) -> None:
        if not _IMAGE_ID.fullmatch(image):
            raise SandboxExecutionError(
                "Sandbox image must be an immutable local image ID sha256:<64 hex>"
            )

    @staticmethod
    def _validate_execution_id(execution_id: str) -> None:
        if not _EXECUTION_ID.fullmatch(execution_id):
            raise SandboxExecutionError("Invalid sandbox execution ID")

    @staticmethod
    def _validate_container_name(container_name: str) -> None:
        if not _CONTAINER_NAME.fullmatch(container_name):
            raise SandboxExecutionError("Invalid Docker container name")

    def build_create_command(
        self,
        *,
        spec: SandboxSpec,
        context: SandboxExecutionContext,
        container_name: str,
        argv: list[str],
        execution_id: str,
        source: Path | None = None,
    ) -> list[str]:
        validate_argv(argv, spec.command_rules)
        self._validate_image(spec.image)
        self._validate_execution_id(execution_id)
        self._validate_container_name(container_name)
        source = source or self.authorize(context)
        if spec.network:
            raise SandboxExecutionError("M2B requires network=false")
        if spec.secrets:
            raise SandboxExecutionError("M2B requires an empty secret set")
        if spec.home_access:
            raise SandboxExecutionError("M2B requires home_access=false")
        reserved = {_OWNER_LABEL, _POLICY_LABEL}
        overlap = reserved.intersection(spec.labels)
        if overlap:
            raise SandboxExecutionError(
                f"Sandbox labels use reserved ownership keys: {sorted(overlap)}"
            )

        command = [
            self.docker_binary,
            "create",
            "--name",
            container_name,
            "--label",
            f"{_OWNER_LABEL}={execution_id}",
            "--label",
            f"{_POLICY_LABEL}={self.policy_snapshot.source_sha256}",
            "--read-only",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(spec.pids_limit),
            "--memory",
            f"{spec.max_memory_mb}m",
            "--cpus",
            str(spec.max_cpu),
            "--user",
            "65534:65534",
            "--env",
            "HOME=/nonexistent",
            "--workdir",
            spec.workspace_mount,
            "--mount",
            f"type=bind,src={source},dst={spec.source_mount},readonly",
            "--tmpfs",
            f"{spec.workspace_mount}:rw,nosuid,nodev,size={spec.max_disk_mb}m,mode=1777",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
        ]
        for key, value in sorted(spec.labels.items()):
            command.extend(["--label", f"{key}={value}"])
        command.append(spec.image)
        command.extend(argv)
        return command

    def _list_exact(self, container_name: str) -> tuple[bool, set[str], str]:
        try:
            listed = subprocess.run(
                [
                    self.docker_binary,
                    "ps",
                    "-a",
                    "--no-trunc",
                    "--filter",
                    f"name=^/{container_name}$",
                    "--format",
                    "{{.Names}}",
                ],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, set(), f"docker ps verification unavailable: {exc}"
        if listed.returncode != 0:
            detail = listed.stderr.strip() or listed.stdout.strip()
            return False, set(), f"docker ps verification failed: {detail}"
        names = {line.strip() for line in listed.stdout.splitlines() if line.strip()}
        return True, names, ""

    def _ensure_name_available(self, container_name: str) -> None:
        ok, names, detail = self._list_exact(container_name)
        if not ok:
            raise SandboxExecutionError(
                f"Cannot prove Docker container name availability: {detail}"
            )
        if names:
            raise SandboxExecutionError(
                f"Docker container name already exists: {sorted(names)}"
            )

    def _inspect_owner(self, container_name: str) -> tuple[bool, str, str]:
        try:
            inspected = subprocess.run(
                [
                    self.docker_binary,
                    "inspect",
                    "--format",
                    f'{{{{ index .Config.Labels "{_OWNER_LABEL}" }}}}',
                    container_name,
                ],
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return False, "", f"docker inspect unavailable: {exc}"
        if inspected.returncode != 0:
            return False, "", inspected.stderr.strip() or inspected.stdout.strip()
        return True, inspected.stdout.strip(), ""

    def _cleanup(self, container_name: str, execution_id: str) -> tuple[bool, str]:
        self._validate_execution_id(execution_id)
        diagnostics: list[str] = []
        exists, owner, inspect_detail = self._inspect_owner(container_name)
        if not exists:
            ok, names, detail = self._list_exact(container_name)
            if not ok:
                diagnostics.extend(item for item in (inspect_detail, detail) if item)
                return False, "; ".join(diagnostics)
            if not names:
                return True, inspect_detail
            diagnostics.append(
                "container exists but ownership could not be verified; cleanup refused"
            )
            if inspect_detail:
                diagnostics.append(inspect_detail)
            return False, "; ".join(diagnostics)
        if owner != execution_id:
            return (
                False,
                "container ownership mismatch; cleanup refused "
                f"(expected={execution_id}, actual={owner or '<missing>'})",
            )

        try:
            removal = subprocess.run(
                [self.docker_binary, "rm", "-f", container_name],
                text=True,
                capture_output=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            diagnostics.append(f"docker rm unavailable: {exc}")
        else:
            if removal.returncode != 0:
                diagnostics.append(
                    f"docker rm failed: {removal.stderr.strip() or removal.stdout.strip()}"
                )

        ok, names, detail = self._list_exact(container_name)
        if not ok:
            diagnostics.append(detail)
            return False, "; ".join(diagnostics)
        if names:
            diagnostics.append(f"container is still listed after cleanup: {sorted(names)}")
            return False, "; ".join(diagnostics)
        return True, "; ".join(diagnostics)

    def run(
        self,
        *,
        spec: SandboxSpec,
        context: SandboxExecutionContext,
        output_dir: str | Path,
        argv: list[str],
        container_name: str | None = None,
    ) -> SandboxResult:
        source = self.authorize(context)
        self._validate_image(spec.image)
        self.preflight()
        execution_id = uuid.uuid4().hex
        name = container_name or f"cos-executor-{execution_id[:12]}"
        self._validate_container_name(name)
        self._ensure_name_available(name)
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        create_command = self.build_create_command(
            spec=spec,
            context=context,
            container_name=name,
            argv=argv,
            execution_id=execution_id,
            source=source,
        )

        create_attempted = False
        timed_out = False
        stdout = ""
        stderr = ""
        exit_code: int | None = None
        cleanup_verified = False
        cleanup_detail = "container creation was not attempted"
        started = time.monotonic()
        try:
            create_attempted = True
            creation = subprocess.run(
                create_command,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if creation.returncode != 0:
                raise SandboxExecutionError(
                    f"docker create failed: {creation.stderr.strip() or creation.stdout.strip()}"
                )
            try:
                execution = subprocess.run(
                    [self.docker_binary, "start", "-a", name],
                    text=True,
                    capture_output=True,
                    timeout=spec.timeout_seconds,
                    check=False,
                )
                stdout = execution.stdout
                stderr = execution.stderr
                exit_code = execution.returncode
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                stdout = (
                    (exc.stdout or "")
                    if isinstance(exc.stdout, str)
                    else (exc.stdout or b"").decode(errors="replace")
                )
                stderr = (
                    (exc.stderr or "")
                    if isinstance(exc.stderr, str)
                    else (exc.stderr or b"").decode(errors="replace")
                )
                subprocess.run(
                    [self.docker_binary, "kill", name],
                    text=True,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                waited = subprocess.run(
                    [self.docker_binary, "wait", name],
                    text=True,
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                try:
                    exit_code = int(waited.stdout.strip())
                except ValueError:
                    exit_code = None
        finally:
            if create_attempted:
                cleanup_verified, cleanup_detail = self._cleanup(name, execution_id)

        if not cleanup_verified:
            stderr = f"{stderr}\nCLEANUP_UNVERIFIED: {cleanup_detail}".strip()
        return SandboxResult(
            container_name=name,
            execution_id=execution_id,
            policy_sha256=self.policy_snapshot.source_sha256,
            argv=tuple(argv),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_seconds=time.monotonic() - started,
            output_dir=output,
            cleanup_verified=cleanup_verified,
        )
