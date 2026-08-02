from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CommandRule:
    executable: str
    argv_prefix: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CommandRule":
        return cls(str(value["executable"]), tuple(str(item) for item in value.get("argv_prefix", [])))

    def matches(self, argv: list[str]) -> bool:
        if not argv or argv[0] != self.executable:
            return False
        prefix = list(self.argv_prefix)
        return argv[1 : 1 + len(prefix)] == prefix


@dataclass(frozen=True)
class SandboxExecutionContext:
    repository: str
    commit: str
    repository_root: Path
    source_dir: Path
    purpose: str

    def to_dict(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "commit": self.commit,
            "repository_root": str(self.repository_root),
            "source_dir": str(self.source_dir),
            "purpose": self.purpose,
        }


@dataclass(frozen=True)
class SandboxSpec:
    image: str
    command_rules: tuple[CommandRule, ...]
    max_cpu: float = 1.0
    max_memory_mb: int = 256
    max_disk_mb: int = 32
    timeout_seconds: int = 30
    pids_limit: int = 64
    network: bool = False
    secrets: tuple[str, ...] = ()
    home_access: bool = False
    source_mount: str = "/source"
    workspace_mount: str = "/workspace"
    labels: dict[str, str] = field(default_factory=lambda: {"creative-os-executor": "sandbox"})

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SandboxSpec":
        return cls(
            image=str(value["image"]),
            command_rules=tuple(CommandRule.from_dict(item) for item in value.get("command_rules", [])),
            max_cpu=float(value.get("max_cpu", 1.0)),
            max_memory_mb=int(value.get("max_memory_mb", 256)),
            max_disk_mb=int(value.get("max_disk_mb", 32)),
            timeout_seconds=int(value.get("timeout_seconds", 30)),
            pids_limit=int(value.get("pids_limit", 64)),
            network=bool(value.get("network", False)),
            secrets=tuple(str(item) for item in value.get("secrets", [])),
            home_access=bool(value.get("home_access", False)),
            source_mount=str(value.get("source_mount", "/source")),
            workspace_mount=str(value.get("workspace_mount", "/workspace")),
            labels={str(k): str(v) for k, v in value.get("labels", {"creative-os-executor": "sandbox"}).items()},
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command_rules"] = [asdict(rule) for rule in self.command_rules]
        return payload


@dataclass(frozen=True)
class SandboxResult:
    container_name: str
    argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    output_dir: Path
    cleanup_verified: bool

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.cleanup_verified
