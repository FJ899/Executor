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
CURRENT_TRUST_PROFILE = ROOT / "trust_profiles/github-p4-pilots.json"
HISTORICAL_TRUST_PROFILE = (
    ROOT / "trust_profiles/github-p4-pilots-pre-transfer-2026-08-16.json"
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

    def test_current_cross_repository_bindings_use_fj899(self):
        policy = json.loads((ROOT / "EXECUTOR_POLICY.yaml").read_text(encoding="utf-8"))
        fixture = json.loads(
            (ROOT / "tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml").read_text(
                encoding="utf-8"
            )
        )
        pointer = (ROOT / "docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md").read_text(
            encoding="utf-8"
        )
        profile = json.loads(CURRENT_TRUST_PROFILE.read_text(encoding="utf-8"))

        self.assertEqual(
            policy["execution"]["controlled_external_fixtures"][0]["repository"],
            "FJ899/executor-pilot-target",
        )
        self.assertEqual(
            [entry["repository"] for entry in policy["execution"]["bounded_pilot_repositories"]],
            ["FJ899/scriptops", "FJ899/creative-os-project-reconstructor"],
        )
        self.assertEqual(
            fixture["repositories"]["target"]["name"],
            "FJ899/executor-pilot-target",
        )
        self.assertIn('canonical_repository: "FJ899/Saddle"', pointer)
        self.assertEqual(profile["intake_repository"], "FJ899/Executor")
        self.assertEqual(profile["allowed_actor"], {"login": "FJ899", "id": 275481581})
        self.assertEqual(
            profile["allowed_target_repositories"],
            ["FJ899/scriptops", "FJ899/creative-os-project-reconstructor"],
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

    def test_pre_transfer_p4_profile_is_preserved_for_frozen_evidence(self):
        historical = json.loads(HISTORICAL_TRUST_PROFILE.read_text(encoding="utf-8"))
        self.assertEqual(historical["intake_repository"], "JTJ07/Executor")
        self.assertEqual(
            historical["allowed_target_repositories"],
            ["JTJ07/scriptops", "JTJ07/creative-os-project-reconstructor"],
        )
        self.assertEqual(
            historical["allowed_actor"],
            {"login": "JTJ07", "id": 219382941},
        )

    def test_pre_transfer_identity_is_not_the_current_project_binding(self):
        project = json.loads(
            (ROOT / "project_contracts/executor-self.yaml").read_text(encoding="utf-8")
        )
        self.assertNotEqual(project["project"]["repository"], PRE_TRANSFER)


if __name__ == "__main__":
    unittest.main()
