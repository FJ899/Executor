from __future__ import annotations

import hashlib
import json
import subprocess
import unittest
from pathlib import Path

from executor.pilot_policy_authority import resolve_pilot_policy_authority
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TASK = ROOT / "tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml"


def _head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _controlled_contract() -> dict:
    raw = CANONICAL_TASK.read_bytes()
    canonical = json.loads(raw.decode("utf-8"))
    golden = canonical["golden_path"]
    target = canonical["repositories"]["target"]
    return {
        "request_id": "gp001-product-authority-e2e-001",
        "target": {
            "repository": target["name"],
            "commit": target["commit"],
            "tree": "1" * 40,
        },
        "formation_binding": {
            "canonical_task_sha256": hashlib.sha256(raw).hexdigest(),
        },
        "authority_boundary": {
            "effect": "BOUNDED_DRAFT_PR_ONLY",
            "merge": False,
            "deploy": False,
            "release": False,
        },
        "task": {
            "problem_statement": golden["problem"]["statement"],
            "allowed_paths": golden["scope"]["allowed_paths"],
            "protected_paths": golden["scope"]["protected_paths"],
            "precondition_argv": [golden["commands"]["target_test_argv"]],
            "postcondition_argv": [golden["commands"]["target_test_argv"]],
            "regression_argv": golden["commands"]["regression_argv"],
            "max_production_files": len(golden["scope"]["allowed_paths"]),
            "max_patch_lines": canonical["budgets"]["max_patch_lines"],
        },
    }


class ProductControlledFixtureAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.commit = _head()
        cls.policy = load_execution_policy_snapshot(ROOT, commit=cls.commit)

    def test_exact_canonical_gp001_uses_existing_controlled_fixture_authority(self) -> None:
        contract = _controlled_contract()
        repository = contract["target"]["repository"]
        commit = contract["target"]["commit"]
        self.assertIsNone(self.policy.bounded_pilot_profile(repository=repository))
        self.assertTrue(
            self.policy.authorizes_controlled_external_fixture(
                task="GP001-FIX-FAILING-TEST-CASE-001",
                repository=repository,
                commit=commit,
            )
        )
        authority = resolve_pilot_policy_authority(
            self.policy,
            contract=contract,
            executor_commit=self.commit,
        )
        self.assertIsNotNone(authority)
        assert authority is not None
        self.assertEqual("CONTROLLED_EXTERNAL_FIXTURE", authority.authority_class)
        self.assertEqual(1, authority.max_production_files)
        self.assertEqual((repository,), authority.bounded_external_repositories)
        self.assertEqual(
            "GP001-FIX-FAILING-TEST-CASE-001",
            authority.controlled_fixture_task_id,
        )

    def test_wrong_canonical_task_hash_fails_closed(self) -> None:
        contract = _controlled_contract()
        contract["formation_binding"]["canonical_task_sha256"] = "0" * 64
        self.assertIsNone(
            resolve_pilot_policy_authority(
                self.policy,
                contract=contract,
                executor_commit=self.commit,
            )
        )

    def test_wrong_target_commit_fails_closed(self) -> None:
        contract = _controlled_contract()
        contract["target"]["commit"] = "f" * 40
        self.assertIsNone(
            resolve_pilot_policy_authority(
                self.policy,
                contract=contract,
                executor_commit=self.commit,
            )
        )

    def test_frozen_task_drift_fails_closed(self) -> None:
        contract = _controlled_contract()
        contract["task"]["allowed_paths"] = ["project_registry/other.py"]
        self.assertIsNone(
            resolve_pilot_policy_authority(
                self.policy,
                contract=contract,
                executor_commit=self.commit,
            )
        )

    def test_non_draft_effect_boundary_fails_closed(self) -> None:
        contract = _controlled_contract()
        contract["authority_boundary"]["merge"] = True
        self.assertIsNone(
            resolve_pilot_policy_authority(
                self.policy,
                contract=contract,
                executor_commit=self.commit,
            )
        )

    def test_existing_generic_bounded_pilot_behavior_is_preserved(self) -> None:
        contract = {
            "target": {
                "repository": "FJ899/scriptops",
                "commit": "a" * 40,
                "tree": "b" * 40,
            },
            "task": {
                "allowed_paths": ["phase6/example.py"],
                "protected_paths": [],
            },
        }
        authority = resolve_pilot_policy_authority(
            self.policy,
            contract=contract,
            executor_commit=self.commit,
        )
        self.assertIsNotNone(authority)
        assert authority is not None
        self.assertEqual("BOUNDED_PILOT_REPOSITORY", authority.authority_class)
        self.assertEqual(3, authority.max_production_files)
        self.assertIn("FJ899/scriptops", authority.bounded_external_repositories)


if __name__ == "__main__":
    unittest.main()
