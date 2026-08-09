import hashlib
import unittest
from pathlib import Path

from executor.contracts import ValidationStatus, load_contract, validate_test_contract
from executor.governance import validate_task_bundle
from executor.gp001_contract import validate_gp001_task_contract


ROOT = Path(__file__).resolve().parents[1]
TASK_PATH = ROOT / "tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml"
TEST_PATH = ROOT / "test_contracts/GP001_FIX_FAILING_TEST_CASE_001.yaml"
POLICY_PATH = ROOT / "EXECUTOR_POLICY.yaml"


class GP001ContractTest(unittest.TestCase):
    def task(self):
        return load_contract(TASK_PATH)

    def validate(self, task):
        return validate_gp001_task_contract(task)

    def test_canonical_gp001_contract_is_structurally_valid(self):
        result = self.validate(self.task())
        self.assertEqual(result.status, ValidationStatus.VALID, result.to_dict())

    def test_contract_pins_case_001_repository_and_test(self):
        task = self.task()
        self.assertEqual(
            task["repositories"]["target"]["name"],
            "litrgratis-pixel/executor-pilot-target",
        )
        self.assertEqual(
            task["repositories"]["target"]["commit"],
            "3934a94a5eebf750079200589d6dc40e024d44a0",
        )
        self.assertEqual(
            task["golden_path"]["problem"]["target_test"],
            "tests.test_registry.ProjectRegistryTests.test_duplicate_batch_does_not_partially_mutate_registry",
        )

    def test_test_contract_hash_is_exactly_bound(self):
        task = self.task()
        actual = hashlib.sha256(TEST_PATH.read_bytes()).hexdigest()
        self.assertEqual(actual, task["test_contract"]["sha256"])

    def test_scope_expansion_cannot_be_enabled(self):
        task = self.task()
        task["golden_path"]["scope"]["scope_expansion"] = "AUTO_EXPAND"
        result = self.validate(task)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("GP001_SCOPE_EXPANSION_FORBIDDEN", {issue.code for issue in result.issues})

    def test_tests_cannot_enter_allowed_scope(self):
        task = self.task()
        task["golden_path"]["scope"]["allowed_paths"].append("tests/test_registry.py")
        result = self.validate(task)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("GP001_SCOPE_OVERLAP", {issue.code for issue in result.issues})

    def test_target_test_file_must_remain_protected(self):
        task = self.task()
        task["golden_path"]["scope"]["protected_paths"] = ["cases/**"]
        result = self.validate(task)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("GP001_TARGET_TEST_NOT_PROTECTED", {issue.code for issue in result.issues})

    def test_mutation_requires_authorization(self):
        task = self.task()
        task["golden_path"]["authorization"]["mutation_requires_authorization"] = False
        result = self.validate(task)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("GP001_MUTATION_REQUIRES_AUTHORIZATION", {issue.code for issue in result.issues})

    def test_deliberation_cannot_expand_contract(self):
        task = self.task()
        task["golden_path"]["discovery"]["may_expand_contract"] = True
        result = self.validate(task)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn(
            "GP001_DELIBERATION_CANNOT_EXPAND_CONTRACT",
            {issue.code for issue in result.issues},
        )

    def test_execution_cannot_self_certify_product_acceptance(self):
        task = self.task()
        task["golden_path"]["result_policy"]["success_status"] = "PASS"
        result = self.validate(task)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("GP001_SELF_ACCEPTANCE_FORBIDDEN", {issue.code for issue in result.issues})

    def test_gp001_test_contract_is_valid_but_waits_for_run_evidence(self):
        result = validate_test_contract(load_contract(TEST_PATH), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertNotIn(
            "CONTRADICTORY_ACCEPTANCE",
            {issue.code for issue in result.issues},
        )

    def test_authoritative_task_waits_for_external_repository_proof(self):
        result = validate_task_bundle(
            self.task(),
            executor_policy=load_contract(POLICY_PATH),
            base_dir=ROOT,
            repository_roots={},
        )
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn(
            "REPOSITORY_COMMIT_UNVERIFIED",
            {issue.code for issue in result.issues},
        )


if __name__ == "__main__":
    unittest.main()
