from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path

from executor.sandbox.command_policy import validate_argv
from executor.sandbox.spec import SandboxResult, SandboxSpec


class SandboxUnavailable(RuntimeError):
    pass


class SandboxExecutionError(RuntimeError):
    pass


class DockerSandboxBackend:
    def __init__(self, *, docker_binary: str = "docker"):
        self.docker_binary = docker_binary

    def preflight(self) -> None:
        binary = shutil.which(self.docker_binary)
        if binary is None:
            raise SandboxUnavailable("Docker CLI is unavailable; host execution fallback is forbidden")
        completed = subprocess.run(
            [binary, "version", "--format", "{{.Server.Version}}"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        if completed.returncode != 0:
            raise SandboxUnavailable(f"Docker daemon is unavailable: {completed.stderr.strip()}")

    def build_create_command(
        self,
        *,
        spec: SandboxSpec,
        source_dir: str | Path,
        container_name: str,
        argv: list[str],
    ) -> list[str]:
        validate_argv(argv, spec.command_rules)
        source = Path(source_dir).resolve()
        if not source.is_dir():
            raise SandboxExecutionError(f"Source directory does not exist: {source}")
        if spec.network:
            raise SandboxExecutionError("M2B requires network=false")
        if spec.secrets:
            raise SandboxExecutionError("M2B requires an empty secret set")
        if spec.home_access:
            raise SandboxExecutionError("M2B requires home_access=false")

        command = [
            self.docker_binary,
            "create",
            "--name",
            container_name,
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

    def run(
        self,
        *,
        spec: SandboxSpec,
        source_dir: str | Path,
        output_dir: str | Path,
        argv: list[str],
        container_name: str | None = None,
    ) -> SandboxResult:
        self.preflight()
        name = container_name or f"cos-executor-{uuid.uuid4().hex[:12]}"
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        create_command = self.build_create_command(spec=spec, source_dir=source_dir, container_name=name, argv=argv)

        created = False
        timed_out = False
        stdout = ""
        stderr = ""
        exit_code: int | None = None
        started = time.monotonic()
        try:
            creation = subprocess.run(create_command, text=True, capture_output=True, timeout=30, check=False)
            if creation.returncode != 0:
                raise SandboxExecutionError(f"docker create failed: {creation.stderr.strip()}")
            created = True
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
                stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else (exc.stdout or b"").decode(errors="replace")
                stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else (exc.stderr or b"").decode(errors="replace")
                subprocess.run([self.docker_binary, "kill", name], text=True, capture_output=True, timeout=10, check=False)
                waited = subprocess.run([self.docker_binary, "wait", name], text=True, capture_output=True, timeout=10, check=False)
                try:
                    exit_code = int(waited.stdout.strip())
                except ValueError:
                    exit_code = None
        finally:
            if created:
                subprocess.run([self.docker_binary, "rm", "-f", name], text=True, capture_output=True, timeout=15, check=False)

        inspected = subprocess.run(
            [self.docker_binary, "inspect", name],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        cleanup_verified = inspected.returncode != 0
        return SandboxResult(
            container_name=name,
            argv=tuple(argv),
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            duration_seconds=time.monotonic() - started,
            output_dir=output,
            cleanup_verified=cleanup_verified,
        )
