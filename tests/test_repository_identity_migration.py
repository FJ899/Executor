import json
import unittest
from pathlib import Path

from executor.request_to_contract import _EXECUTOR_REPOSITORY
from executor.sandbox.docker import DockerSandboxBackend
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot


ROOT = Path(__file__).resolve().parents[1]
CURRENT = "FJ899/Executor"
PRE_TRANSFER = "JTJ07/Executor"
HISTORICAL_ACCEPTANCE = (
    ROOT / "docs/governance/EXECUTOR_1_0_FINAL_HUMAN_ACCEPTANCE_RECORD_2026-08-20.md"
)


class RepositoryIdentityMigrationTest(unittest.TestCase):
    def test_current_repository_surfaces_are_rebound_to_fj899(self):
        project = json.loads(
            (ROOT / "project_contracts/executor-self.yaml").read_text(encoding="utf-8")
        )
        task = json.loads(
            (ROOT / "tasks/examples/EXECUTOR_TASK_FIXTURE-001.yaml").read_text(
                encoding="utf-8"
            )
        )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        authority = (ROOT / "docs/governance/DOCUMENT_AUTHORITY.md").read_text(
            encoding="utf-8"
        )
        workflow = (ROOT / ".github/workflows/verify.yml").read_text(
            encoding="utf-8"
        )

        self.assertEqual(project["project"]["repository"], CURRENT)
        self.assertEqual(task["repositories"]["target"]["name"], CURRENT)
        self.assertIn("Repozytorium: `FJ899/Executor`.", readme)
        self.assertIn('repository: "FJ899/Executor"', authority)
        self.assertIn("--repository-root FJ899/Executor=.", workflow)
        self.assertIn("--repository FJ899/Executor", workflow)
        self.assertNotIn("--repository-root JTJ07/Executor=.", workflow)
        self.assertNotIn("--repository JTJ07/Executor", workflow)
        self.assertEqual(_EXECUTOR_REPOSITORY, CURRENT)
        self.assertEqual(
            DockerSandboxBackend.__init__.__kwdefaults__["control_repository"],
            CURRENT,
        )

    def test_policy_snapshot_default_is_current_repository(self):
        defaults = load_execution_policy_snapshot.__kwdefaults__
        self.assertIsNotNone(defaults)
        self.assertEqual(defaults["repository"], CURRENT)

    def test_dated_human_acceptance_preserves_pre_transfer_identity(self):
        historical = HISTORICAL_ACCEPTANCE.read_text(encoding="utf-8")
        self.assertIn('repository: "JTJ07/Executor"', historical)
        self.assertIn("REPOSITORY: JTJ07/Executor", historical)
        self.assertNotIn('repository: "FJ899/Executor"', historical)

    def test_pre_transfer_identity_is_not_the_current_project_binding(self):
        project = json.loads(
            (ROOT / "project_contracts/executor-self.yaml").read_text(encoding="utf-8")
        )
        self.assertNotEqual(project["project"]["repository"], PRE_TRANSFER)


if __name__ == "__main__":
    unittest.main()
