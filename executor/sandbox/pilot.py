from __future__ import annotations

from pathlib import Path

from executor.pilot_case_001 import (
    CASE_001_CONTRACT,
    PilotCase001Contract,
    PilotCase001PolicyError,
    verify_case_001_output_checkout,
)
from executor.repository_snapshot import RepositorySnapshotError, verify_source_tree
from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError
from executor.sandbox.spec import SandboxExecutionContext


class PilotCase001DockerSandboxBackend(DockerSandboxBackend):
    """Narrow external-project exception for the pinned CASE-001 pilot only."""

    def __init__(
        self,
        *,
        policy_snapshot,
        contract: PilotCase001Contract = CASE_001_CONTRACT,
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
                "CASE-001 pilot requires global external project execution to remain disabled"
            )
        if policy.auto_merge:
            raise SandboxExecutionError("CASE-001 pilot forbids auto merge")
        if policy.default_network or policy.default_secrets:
            raise SandboxExecutionError(
                "CASE-001 pilot requires network=false and no default secrets"
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
            root = verify_case_001_output_checkout(
                context.repository_root,
                output_commit=context.commit,
                contract=self.contract,
            )
        except PilotCase001PolicyError as exc:
            raise SandboxExecutionError(f"Unverified CASE-001 output: {exc}") from exc

        try:
            source = Path(context.source_dir).resolve(strict=True)
        except OSError as exc:
            raise SandboxExecutionError(
                f"CASE-001 source cannot be resolved: {exc}"
            ) from exc
        if source != root:
            raise SandboxExecutionError(
                "CASE-001 sandbox must mount the verified output repository root"
            )
        try:
            verify_source_tree(root, commit=context.commit, source_dir=root)
        except RepositorySnapshotError as exc:
            raise SandboxExecutionError(
                f"CASE-001 source does not match the output commit: {exc}"
            ) from exc
        return root
