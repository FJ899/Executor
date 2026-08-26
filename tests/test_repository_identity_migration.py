import json
import unittest
from pathlib import Path

from executor.execution_environment import (
    ExecutionEnvironmentError,
    validate_execution_environment,
)
from executor.request_to_contract import _EXECUTOR_REPOSITORY
from executor.sandbox.docker import DockerSandboxBackend
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot


ROOT = Path(__file__).resolve().parents[1]
CURRENT = "FJ899/Executor"
PRE_TRANSFER = "JTJ07/Executor"
CURRENT_PRODUCT_EXECUTION_WORKFLOW = ".github/workflows/gp001-product-execution-recovery.yml"
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
        replay_workflow = (ROOT / ".github/workflows/gp001-replay.yml").read_text(
            encoding="utf-8"
        )
        real_e2e_workflow = (ROOT / ".github/workflows/gp001-real-e2e.yml").read_text(
            encoding="utf-8"
        )
        replay_tool = (ROOT / "tools/run_gp001_real_e2e.py").read_text(encoding="utf-8")

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
        for workflow in (replay_workflow, real_e2e_workflow):
            self.assertIn("https://github.com/FJ899/executor-pilot-target.git", workflow)
            self.assertNotIn("https://github.com/litrgratis-pixel/executor-pilot-target.git", workflow)
        self.assertIn('FIXTURE_REPOSITORY = "FJ899/executor-pilot-target"', replay_tool)

    def test_current_product_execution_environment_uses_fj899_only(self):
        image = "sha256:" + "1" * 64
        current = {
            "schema_version": "executor-execution-environment/1.0",
            "provider": "GITHUB_ACTIONS",
            "repository": CURRENT,
            "executor_commit": "e" * 40,
            "workflow_path": CURRENT_PRODUCT_EXECUTION_WORKFLOW,
            "workflow_sha256": "d" * 64,
            "workflow_run_id": "12345",
            "workflow_run_attempt": "1",
            "workflow_job": "product-execution-recovery",
            "sandbox_image_id": image,
        }
        self.assertEqual(
            validate_execution_environment(
                current,
                executor_commit="e" * 40,
                image_id=image,
            )["repository"],
            CURRENT,
        )
        stale = dict(current)
        stale["repository"] = PRE_TRANSFER
        with self.assertRaises(ExecutionEnvironmentError):
            validate_execution_environment(
                stale,
                executor_commit="e" * 40,
                image_id=image,
            )
        historical_workflow = dict(current)
        historical_workflow["workflow_path"] = ".github/workflows/p4-real-pilots-one-shot.yml"
        with self.assertRaises(ExecutionEnvironmentError):
            validate_execution_environment(
                historical_workflow,
                executor_commit="e" * 40,
                image_id=image,
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
