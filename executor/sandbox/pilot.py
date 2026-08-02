from __future__ import annotations

from executor.pilot_case_001 import CASE_001_CONTRACT, PilotCase001Contract
from executor.pilot_core import PinnedPilotDockerSandboxBackend


class PilotCase001DockerSandboxBackend(PinnedPilotDockerSandboxBackend):
    """Compatibility wrapper for the pinned CASE-001 sandbox boundary."""

    def __init__(
        self,
        *,
        policy_snapshot,
        contract: PilotCase001Contract = CASE_001_CONTRACT,
        docker_binary: str = "docker",
    ) -> None:
        super().__init__(
            policy_snapshot=policy_snapshot,
            contract=contract,
            docker_binary=docker_binary,
        )
