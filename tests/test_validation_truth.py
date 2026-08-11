import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from executor.contracts import ContractLoadError, ValidationStatus, load_contract, validate_project_contract, validate_task_contract, validate_test_contract
from executor.governance import validate_project_bundle, validate_task_bundle

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
POLICY = ROOT / "EXECUTOR_POLICY.yaml"
PROJECT = ROOT / "project_contracts/executor-self.yaml"
TASK_FIXTURE = ROOT / "tasks/examples/EXECUTOR_TASK_FIXTURE-001.yaml"
GINSENG_TASK = ROOT / "tasks/examples/GINSENG_TEST-003.yaml"
CURRENT_EXECUTOR_REPOSITORY = "JTJ07/Executor"


class ValidationTruthTest(unittest.TestCase):
    def policy(self):
        return load_contract(POLICY)

    def test_structural_project_validity_is_not_execution_readiness(self):
        result = validate_project_contract(load_contract(PROJECT))
        self.assertEqual(result.status, ValidationStatus.VALID)
        self.assertFalse(result.authoritative)
        self.assertFalse(result.ready_for_model)
        self.assertFalse(result.ok)
        self.assertEqual(result.execution_status, "BLOCKED_BEFORE_MODEL")

    def test_structural_task_validity_cannot_unlock_ginseng_placeholders(self):
        result = validate_task_contract(load_contract(GINSENG_TASK))
        self.assertEqual(result.status, ValidationStatus.VALID)
        self.assertFalse(result.authoritative)
        self.assertFalse(result.ready_for_model)
        self.assertFalse(result.ok)
        self.assertEqual(result.execution_status, "BLOCKED_BEFORE_MODEL")

    def test_authoritative_bundles_can_be_ready(self):
        project = validate_project_bundle(load_contract(PROJECT), executor_policy=self.policy(), base_dir=ROOT)
        task = validate_task_bundle(
            load_contract(TASK_FIXTURE),
            executor_policy=self.policy(),
            base_dir=ROOT,
            repository_roots={CURRENT_EXECUTOR_REPOSITORY: ROOT},
        )
        for result in (project, task):
            self.assertEqual(result.status, ValidationStatus.VALID)
            self.assertTrue(result.authoritative)
            self.assertTrue(result.ready_for_model)
            self.assertTrue(result.ok)
            self.assertEqual(result.execution_status, "READY_FOR_MODEL")

    def test_direct_contract_loader_is_strict(self):
        documents = (
            '{"a":1,"a":2}',
            '{"value":NaN}',
            '{"value":Infinity}',
            '{"value":-Infinity}',
        )
        for document in documents:
            with self.subTest(document=document), tempfile.TemporaryDirectory() as temp_name:
                path = Path(temp_name) / "contract.json"
                path.write_text(document, encoding="utf-8")
                with self.assertRaises(ContractLoadError):
                    load_contract(path)

    def _valid_test_contract(self):
        return load_contract(ROOT / "test_contracts/examples/valid_test.yaml")

    def _write_test_support(self, base: Path, contract: dict, *, source_path: str, holdout_path: str) -> dict:
        source = base / source_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('{"blocking_gate_count":7}\n', encoding="utf-8")
        holdout = base / holdout_path
        holdout.parent.mkdir(parents=True, exist_ok=True)
        holdout.write_text("SEALED_TEST_FIXTURE_V1\npayload: truth-boundary\n", encoding="utf-8")
        contract["source_claims"][0]["source"]["file"] = source_path
        contract["holdout"]["location"] = holdout_path
        return {
            "schema_version": "executor-holdout-evidence/1.0",
            "attestation_id": "truth-boundary",
            "test_id": contract["test_id"],
            "location": holdout_path,
            "artifact_sha256": hashlib.sha256(holdout.read_bytes()).hexdigest(),
            "visibility": "HIDDEN_FROM_IMPLEMENTER",
            "access": "REPLAY_ONLY",
            "verifier_role": "TEST_FIXTURE_VERIFIER",
            "verifier": "truth-boundary-test",
        }

    def test_source_parent_symlink_is_invalid_even_when_target_stays_inside_root(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            real = base / "real"
            real.mkdir()
            (base / "link").symlink_to(real, target_is_directory=True)
            contract = self._valid_test_contract()
            evidence = self._write_test_support(base, contract, source_path="real/source.json", holdout_path="holdout/fixture.enc")
            contract["source_claims"][0]["source"]["file"] = "link/source.json"
            result = validate_test_contract(contract, base_dir=base, holdout_evidence=evidence)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_SOURCE_PATH", {issue.code for issue in result.issues})

    def test_source_hardlink_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            contract = self._valid_test_contract()
            evidence = self._write_test_support(base, contract, source_path="source.json", holdout_path="holdout/fixture.enc")
            os.link(base / "source.json", base / "source-copy.json")
            result = validate_test_contract(contract, base_dir=base, holdout_evidence=evidence)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_SOURCE_PATH", {issue.code for issue in result.issues})

    def test_holdout_parent_symlink_is_invalid_even_when_target_stays_inside_root(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            real = base / "real"
            real.mkdir()
            (base / "link").symlink_to(real, target_is_directory=True)
            contract = self._valid_test_contract()
            evidence = self._write_test_support(base, contract, source_path="source.json", holdout_path="real/fixture.enc")
            contract["holdout"]["location"] = "link/fixture.enc"
            evidence["location"] = "link/fixture.enc"
            result = validate_test_contract(contract, base_dir=base, holdout_evidence=evidence)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_HOLDOUT_PATH", {issue.code for issue in result.issues})

    def test_holdout_hardlink_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            contract = self._valid_test_contract()
            evidence = self._write_test_support(base, contract, source_path="source.json", holdout_path="holdout/fixture.enc")
            os.link(base / "holdout/fixture.enc", base / "holdout/fixture-copy.enc")
            result = validate_test_contract(contract, base_dir=base, holdout_evidence=evidence)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_HOLDOUT_PATH", {issue.code for issue in result.issues})

    def _minimal_project_tree(self, base: Path) -> tuple[dict, dict]:
        policy = self.policy()
        (base / "README.md").write_text("fixture\n", encoding="utf-8")
        (base / "EXECUTOR_POLICY.yaml").write_text(json.dumps(policy), encoding="utf-8")
        project = load_contract(PROJECT)
        project["project"]["entrypoint"] = "README.md"
        project["authoritative_sources"] = [
            {"path": "EXECUTOR_POLICY.yaml", "role": "authoritative_instruction"},
            {"path": "docs/source.md", "role": "evidence"},
        ]
        return project, policy

    def test_authoritative_project_source_parent_symlink_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            project, policy = self._minimal_project_tree(base)
            real = base / "real"
            real.mkdir()
            (real / "source.md").write_text("evidence\n", encoding="utf-8")
            (base / "docs").symlink_to(real, target_is_directory=True)
            result = validate_project_bundle(project, executor_policy=policy, base_dir=base)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_PROJECT_SOURCE", {issue.code for issue in result.issues})

    def test_authoritative_project_source_hardlink_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            project, policy = self._minimal_project_tree(base)
            (base / "docs").mkdir()
            source = base / "docs/source.md"
            source.write_text("evidence\n", encoding="utf-8")
            os.link(source, base / "source-copy.md")
            result = validate_project_bundle(project, executor_policy=policy, base_dir=base)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_PROJECT_SOURCE", {issue.code for issue in result.issues})

    def test_locked_test_contract_parent_symlink_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            outside = base / "real"
            outside.mkdir()
            test_path = outside / "test.json"
            test_path.write_text("{}\n", encoding="utf-8")
            (base / "contracts").symlink_to(outside, target_is_directory=True)
            task = load_contract(TASK_FIXTURE)
            task["test_contract"] = {
                "path": "contracts/test.json",
                "sha256": hashlib.sha256(test_path.read_bytes()).hexdigest(),
            }
            result = validate_task_bundle(
                task,
                executor_policy=self.policy(),
                base_dir=base,
                repository_roots={CURRENT_EXECUTOR_REPOSITORY: ROOT},
            )
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_TEST_CONTRACT_PATH", {issue.code for issue in result.issues})


if __name__ == "__main__":
    unittest.main()
