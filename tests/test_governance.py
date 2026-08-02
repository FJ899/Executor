import copy
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from executor.cli import main
from executor.contracts import ValidationStatus, load_contract
from executor.governance import validate_project_bundle, validate_task_bundle
from executor.policy import ObjectionKind, normalize_model_objection

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "EXECUTOR_POLICY.yaml"
PROJECT_PATH = ROOT / "project_contracts/executor-self.yaml"
TASK_FIXTURE_PATH = ROOT / "tasks/examples/EXECUTOR_TASK_FIXTURE-001.yaml"
GINSENG_TASK_PATH = ROOT / "tasks/examples/GINSENG_TEST-003.yaml"


class GovernanceTest(unittest.TestCase):
    def policy(self):
        return load_contract(POLICY_PATH)

    def project(self):
        return load_contract(PROJECT_PATH)

    def task_fixture(self):
        return load_contract(TASK_FIXTURE_PATH)

    def test_valid_project_bundle(self):
        result = validate_project_bundle(self.project(), executor_policy=self.policy(), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.VALID)

    def test_project_requires_executor_policy(self):
        result = validate_project_bundle(self.project(), executor_policy=None, base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("EXECUTOR_POLICY_REQUIRED", {issue.code for issue in result.issues})

    def test_project_cannot_override_policy_network(self):
        project = self.project()
        project["capabilities"]["network"]["default"] = True
        result = validate_project_bundle(project, executor_policy=self.policy(), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("POLICY_PRECEDENCE_VIOLATION", {issue.code for issue in result.issues})

    def test_project_authoritative_source_must_exist(self):
        project = self.project()
        project["authoritative_sources"].append({"path": "missing-authoritative-source.md", "role": "evidence"})
        result = validate_project_bundle(project, executor_policy=self.policy(), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("PROJECT_SOURCE_NOT_FOUND", {issue.code for issue in result.issues})

    def test_provided_policy_must_match_authoritative_file(self):
        policy = self.policy()
        policy["execution"]["default_network"] = True
        result = validate_project_bundle(self.project(), executor_policy=policy, base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("POLICY_FILE_MISMATCH", {issue.code for issue in result.issues})

    def test_valid_locked_task_fixture(self):
        result = validate_task_bundle(self.task_fixture(), executor_policy=self.policy(), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.VALID)

    def test_ginseng_placeholder_locks_are_invalid(self):
        result = validate_task_bundle(load_contract(GINSENG_TASK_PATH), executor_policy=self.policy(), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        codes = {issue.code for issue in result.issues}
        self.assertIn("UNLOCKED_REPOSITORY", codes)
        self.assertIn("UNLOCKED_TEST_CONTRACT", codes)

    def test_task_contract_hash_is_verified(self):
        task = self.task_fixture()
        task["test_contract"]["sha256"] = "1" * 64
        result = validate_task_bundle(task, executor_policy=self.policy(), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("TEST_CONTRACT_HASH_MISMATCH", {issue.code for issue in result.issues})

    def test_task_cannot_override_policy_network(self):
        task = self.task_fixture()
        task["capabilities"]["network"] = True
        result = validate_task_bundle(task, executor_policy=self.policy(), base_dir=ROOT)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("POLICY_PRECEDENCE_VIOLATION", {issue.code for issue in result.issues})

    def test_model_cannot_self_certify_hard_veto(self):
        objection = normalize_model_objection({
            "kind": "HARD_VETO",
            "summary": "I found a deterministic violation",
            "evidence_type": "contract_invalid",
            "evidence": {"path": "task.json", "code": "INVALID"},
        })
        self.assertEqual(objection.kind, ObjectionKind.EVIDENCE_GAP)

    def test_cli_validates_project_with_policy(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([
                "validate-project",
                str(PROJECT_PATH),
                "--policy",
                str(POLICY_PATH),
                "--base-dir",
                str(ROOT),
            ])
        self.assertEqual(code, 0)
        self.assertIn("READY_FOR_MODEL", out.getvalue())

    def test_cli_blocks_unlocked_ginseng_task(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([
                "validate-task",
                str(GINSENG_TASK_PATH),
                "--policy",
                str(POLICY_PATH),
                "--base-dir",
                str(ROOT),
            ])
        self.assertEqual(code, 2)
        self.assertIn("UNLOCKED_REPOSITORY", out.getvalue())
        self.assertIn("UNLOCKED_TEST_CONTRACT", out.getvalue())


if __name__ == "__main__":
    unittest.main()
