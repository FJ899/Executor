import hashlib
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from executor.cli import main
from executor.contracts import ValidationStatus, load_contract, validate_project_contract, validate_task_contract, validate_test_contract
from executor.policy import ObjectionKind, PolicyEngine, normalize_model_objection, wrap_repository_content

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class FoundationsTest(unittest.TestCase):
    def project(self):
        return load_contract(ROOT / "project_contracts/executor-self.yaml")

    def valid_test_contract(self):
        return load_contract(ROOT / "test_contracts/examples/valid_test.yaml")

    def holdout_evidence(self, contract=None, base_dir=FIXTURES):
        contract = contract or self.valid_test_contract()
        location = contract["holdout"]["location"]
        payload = (Path(base_dir) / location).read_bytes()
        test_id = contract["test_id"]
        return {
            "schema_version": "executor-holdout-evidence/1.0",
            "attestation_id": f"test-{test_id}",
            "test_id": test_id,
            "location": location,
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "visibility": "HIDDEN_FROM_IMPLEMENTER",
            "access": "REPLAY_ONLY",
            "verifier_role": "TEST_FIXTURE_VERIFIER" if test_id.startswith("EXECUTOR_VALIDATOR_FIXTURE-") else "INDEPENDENT_HOLDOUT_VERIFIER",
            "verifier": "test-verifier",
        }

    def validate_test(self, contract, *, base_dir=FIXTURES, include_holdout_evidence=True):
        evidence = self.holdout_evidence(contract, base_dir) if include_holdout_evidence and base_dir is not None else None
        return validate_test_contract(contract, base_dir=base_dir, holdout_evidence=evidence)

    def assert_acceptance_contradiction(self, *assertions):
        contract = self.valid_test_contract()
        contract["acceptance"] = list(assertions)
        result = self.validate_test(contract)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("CONTRADICTORY_ACCEPTANCE", {issue.code for issue in result.issues})

    def assert_acceptance_not_contradictory(self, *assertions):
        contract = self.valid_test_contract()
        contract["acceptance"] = list(assertions)
        result = self.validate_test(contract)
        self.assertEqual(result.status, ValidationStatus.VALID)
        self.assertNotIn("CONTRADICTORY_ACCEPTANCE", {issue.code for issue in result.issues})

    def validate_source_text(self, source_text):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            contract = self.valid_test_contract()
            holdout_path = base / contract["holdout"]["location"]
            holdout_path.parent.mkdir(parents=True)
            (base / "source.json").write_text(source_text, encoding="utf-8")
            holdout_path.write_text("SEALED_TEST_FIXTURE_V1\npayload: source-test\n", encoding="utf-8")
            contract["source_claims"][0]["source"]["file"] = "source.json"
            return self.validate_test(contract, base_dir=base)

    def test_valid_test_contract(self):
        result = self.validate_test(self.valid_test_contract())
        self.assertEqual(result.status, ValidationStatus.VALID)
        self.assertEqual(result.execution_status, "READY_FOR_MODEL")

    def test_holdout_declaration_without_external_evidence_is_gap(self):
        result = self.validate_test(self.valid_test_contract(), include_holdout_evidence=False)
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("HOLDOUT_VISIBILITY_UNVERIFIED", {issue.code for issue in result.issues})

    def test_holdout_evidence_must_bind_artifact_hash(self):
        contract = self.valid_test_contract()
        evidence = self.holdout_evidence(contract)
        evidence["artifact_sha256"] = "0" * 64
        result = validate_test_contract(contract, base_dir=FIXTURES, holdout_evidence=evidence)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("HOLDOUT_EVIDENCE_MISMATCH", {issue.code for issue in result.issues})

    def test_placeholder_holdout_is_evidence_gap(self):
        with tempfile.TemporaryDirectory() as temp_name:
            base = Path(temp_name)
            contract = self.valid_test_contract()
            (base / "source_result.json").write_text('{"blocking_gate_count": 7}\n', encoding="utf-8")
            holdout_path = base / contract["holdout"]["location"]
            holdout_path.parent.mkdir(parents=True)
            holdout_path.write_text("HOLDOUT PLACEHOLDER\n", encoding="utf-8")
            result = validate_test_contract(contract, base_dir=base, holdout_evidence=None)
            self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
            self.assertIn("HOLDOUT_CONTENT_UNUSABLE", {issue.code for issue in result.issues})

    def test_holdout_symlink_cannot_escape_base_dir(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            base = root / "base"
            outside = root / "outside"
            base.mkdir()
            outside.mkdir()
            contract = self.valid_test_contract()
            (base / "source_result.json").write_text('{"blocking_gate_count": 7}\n', encoding="utf-8")
            outside_holdout = outside / "holdout.enc"
            outside_holdout.write_text("SEALED\n", encoding="utf-8")
            holdout_path = base / contract["holdout"]["location"]
            holdout_path.parent.mkdir(parents=True)
            holdout_path.symlink_to(outside_holdout)
            result = validate_test_contract(contract, base_dir=base, holdout_evidence=None)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_HOLDOUT_PATH", {issue.code for issue in result.issues})

    def test_fixture_verifier_cannot_attest_production_test(self):
        contract = self.valid_test_contract()
        contract["test_id"] = "GINSENG_TEST-003"
        evidence = self.holdout_evidence(self.valid_test_contract())
        evidence["test_id"] = contract["test_id"]
        evidence["verifier_role"] = "TEST_FIXTURE_VERIFIER"
        result = validate_test_contract(contract, base_dir=FIXTURES, holdout_evidence=evidence)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("INVALID_HOLDOUT_VERIFIER", {issue.code for issue in result.issues})

    def test_missing_negative_blocks_before_model(self):
        contract = load_contract(ROOT / "test_contracts/examples/invalid_missing_negative.yaml")
        result = validate_test_contract(contract, base_dir=FIXTURES)
        self.assertEqual(result.execution_status, "BLOCKED_BEFORE_MODEL")
        self.assertIn("MISSING_CONTROL", {x.code for x in result.issues})

    def test_contradictory_acceptance(self):
        contract = self.valid_test_contract()
        contract["acceptance"].append("blocking_gate_count_after == 5")
        self.assertIn("CONTRADICTORY_ACCEPTANCE", {x.code for x in self.validate_test(contract).issues})

    def test_equivalent_numeric_acceptance_is_contradictory(self):
        counterexamples = (
            ("score == 1", "score != 1.0"),
            ("score != 1.0", "score == 1"),
        )
        for first, second in counterexamples:
            with self.subTest(first=first, second=second):
                self.assert_acceptance_contradiction(first, second)

    def test_equivalent_json_acceptance_is_contradictory(self):
        counterexamples = (
            ('payload == {"a":1,"b":2}', 'payload != {"b":2,"a":1}'),
            ('mode == "READY"', 'mode != "\\u0052EADY"'),
            ('payload == {"items":[1,{"score":2}]}', 'payload != {"items":[1.0,{"score":2.0}]}'),
        )
        for required, denied in counterexamples:
            with self.subTest(required=required, denied=denied):
                self.assert_acceptance_contradiction(required, denied)

    def test_distinct_json_types_are_not_contradictory(self):
        counterexamples = (
            ("flag == true", "flag != 1"),
            ('payload == {"flag":true}', 'payload != {"flag":1}'),
            ("payload == [true]", "payload != [1]"),
            ('payload == {"items":[{"flag":true}]}', 'payload != {"items":[{"flag":1}]}'),
            ('payload != {"flag":1}', 'payload == {"flag":true}'),
        )
        for first, second in counterexamples:
            with self.subTest(first=first, second=second):
                self.assert_acceptance_not_contradictory(first, second)

    def test_nonstandard_acceptance_literals_are_not_silently_normalized(self):
        self.assert_acceptance_contradiction("value == NaN", "value != NaN")
        self.assert_acceptance_not_contradictory("value == NaN", "value != Infinity")
        duplicate = 'payload == {"a":1,"a":2}'
        self.assert_acceptance_contradiction(duplicate, duplicate.replace(" == ", " != "))
        self.assert_acceptance_not_contradictory(duplicate, 'payload != {"a":2}')

    def test_visible_holdout(self):
        contract = self.valid_test_contract()
        contract["holdout"]["visibility"] = "VISIBLE_TO_IMPLEMENTER"
        self.assertIn("HOLDOUT_VISIBLE", {x.code for x in self.validate_test(contract).issues})

    def test_missing_source_is_evidence_gap(self):
        contract = self.valid_test_contract()
        contract["source_claims"][0]["source"]["file"] = "missing.json"
        self.assertEqual(self.validate_test(contract).status, ValidationStatus.INSUFFICIENT_EVIDENCE)

    def test_false_source_claim_is_evidence_gap(self):
        contract = self.valid_test_contract()
        contract["source_claims"][0]["claim"] = "blocking_gate_count_before == 999"
        result = self.validate_test(contract)
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("SOURCE_CLAIM_MISMATCH", {issue.code for issue in result.issues})

    def test_missing_source_selector_target_is_evidence_gap(self):
        contract = self.valid_test_contract()
        contract["source_claims"][0]["source"]["selector"] = "$.field_that_does_not_exist"
        result = self.validate_test(contract)
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("SOURCE_SELECTOR_NOT_FOUND", {issue.code for issue in result.issues})

    def test_source_claim_requires_base_dir(self):
        result = validate_test_contract(self.valid_test_contract())
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("SOURCE_BASE_DIR_REQUIRED", {issue.code for issue in result.issues})
        self.assertIn("HOLDOUT_BASE_DIR_REQUIRED", {issue.code for issue in result.issues})

    def test_unsupported_source_selector_is_invalid(self):
        contract = self.valid_test_contract()
        contract["source_claims"][0]["source"]["selector"] = "$..blocking_gate_count"
        result = self.validate_test(contract)
        self.assertEqual(result.status, ValidationStatus.INVALID)
        self.assertIn("INVALID_SOURCE_SELECTOR", {issue.code for issue in result.issues})

    def test_source_symlink_cannot_escape_base_dir(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            base = root / "base"
            outside = root / "outside"
            contract = self.valid_test_contract()
            holdout_path = base / contract["holdout"]["location"]
            holdout_path.parent.mkdir(parents=True)
            outside.mkdir()
            (outside / "source.json").write_text('{"blocking_gate_count": 7}\n', encoding="utf-8")
            (base / "source-link.json").symlink_to(outside / "source.json")
            holdout_path.write_text("SEALED_TEST_FIXTURE_V1\npayload: source-link-test\n", encoding="utf-8")
            contract["source_claims"][0]["source"]["file"] = "source-link.json"
            result = self.validate_test(contract, base_dir=base)
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("UNSAFE_SOURCE_PATH", {issue.code for issue in result.issues})

    def test_duplicate_source_json_key_is_evidence_gap(self):
        result = self.validate_source_text('{"blocking_gate_count": 999, "blocking_gate_count": 7}\n')
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("SOURCE_FILE_INVALID", {issue.code for issue in result.issues})

    def test_nonstandard_source_json_constant_is_evidence_gap(self):
        result = self.validate_source_text('{"blocking_gate_count": NaN}\n')
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("SOURCE_FILE_INVALID", {issue.code for issue in result.issues})

    def test_tamper_must_be_detected(self):
        contract = self.valid_test_contract()
        contract["tamper_control"]["expected"] = "PASS"
        self.assertIn("TAMPER_MUST_BE_DETECTED", {x.code for x in self.validate_test(contract).issues})

    def test_valid_project(self):
        self.assertEqual(validate_project_contract(self.project()).status, ValidationStatus.VALID)

    def test_default_path_rule_required(self):
        contract = self.project()
        del contract["path_rules"]["**"]
        self.assertIn("MISSING_DEFAULT_PATH_RULE", {x.code for x in validate_project_contract(contract).issues})

    def test_home_access_denied(self):
        contract = self.project()
        contract["environment"]["home_access"] = True
        self.assertIn("HOME_ACCESS_MUST_BE_FALSE", {x.code for x in validate_project_contract(contract).issues})

    def test_authoritative_instruction_required(self):
        contract = self.project()
        [x.update(role="evidence") for x in contract["authoritative_sources"]]
        self.assertIn("NO_PROJECT_INSTRUCTION", {x.code for x in validate_project_contract(contract).issues})

    def test_task_valid(self):
        self.assertEqual(validate_task_contract(load_contract(ROOT / "tasks/examples/GINSENG_TEST-003.yaml")).status, ValidationStatus.VALID)

    def test_auto_merge_forbidden(self):
        task = load_contract(ROOT / "tasks/examples/GINSENG_TEST-003.yaml")
        task["merge_policy"]["mode"] = "AUTO_MERGE"
        self.assertIn("AUTO_MERGE_FORBIDDEN", {x.code for x in validate_task_contract(task).issues})

    def test_forbidden_path_hard_veto(self):
        self.assertEqual(PolicyEngine(self.project()).check_forbidden_path("CREATIVE_OS.md", ["executor/**", "tests/**"]).kind, ObjectionKind.HARD_VETO)

    def test_allowed_path(self):
        self.assertEqual(PolicyEngine(self.project()).check_forbidden_path("executor/cli.py", ["executor/**"]).kind, ObjectionKind.PASS)

    def test_network_secret_denied(self):
        self.assertEqual([x.kind for x in PolicyEngine(self.project()).check_capabilities(network=True, secrets=["PROD_TOKEN"])], [ObjectionKind.HARD_VETO, ObjectionKind.HARD_VETO])

    def test_command_denied(self):
        self.assertEqual(PolicyEngine(self.project()).check_capabilities(command="curl https://example.com")[0].kind, ObjectionKind.HARD_VETO)

    def test_semantic_path_user(self):
        self.assertEqual(PolicyEngine(self.project()).check_path_change("EXECUTOR_POLICY.yaml").kind, ObjectionKind.POLICY_VETO)

    def test_semantic_impact_escalates(self):
        self.assertEqual(PolicyEngine(self.project()).check_path_change("executor/cli.py", result_semantics_change=True).kind, ObjectionKind.POLICY_VETO)

    def test_model_hard_veto_without_evidence(self):
        self.assertEqual(normalize_model_objection({"kind": "HARD_VETO", "summary": "feels risky"}).kind, ObjectionKind.EVIDENCE_GAP)

    def test_prompt_injection_is_untrusted(self):
        content = (FIXTURES / "untrusted_prompt.md").read_text()
        wrapped = wrap_repository_content(repository="x/y", commit="abc", path="docs/note.md", content=content, project_contract=self.project())
        self.assertEqual(wrapped["trust"], "untrusted_data")
        self.assertFalse(wrapped["can_instruct_executor"])

    def test_authoritative_cannot_override_policy(self):
        wrapped = wrap_repository_content(repository="litrgratis-pixel/Executor", commit="abc", path="EXECUTOR_POLICY.yaml", content="{}", project_contract=self.project())
        self.assertTrue(wrapped["can_instruct_executor"])
        self.assertIn("executor_policy", wrapped["cannot_override"])

    def test_cli_valid(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([
                "validate-test",
                str(ROOT / "test_contracts/examples/valid_test.yaml"),
                "--base-dir",
                str(FIXTURES),
                "--holdout-evidence",
                str(FIXTURES / "holdout_evidence.json"),
            ])
        self.assertEqual(code, 0)
        self.assertIn("READY_FOR_MODEL", out.getvalue())

    def test_cli_requires_holdout_evidence(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["validate-test", str(ROOT / "test_contracts/examples/valid_test.yaml"), "--base-dir", str(FIXTURES)])
        self.assertEqual(code, 2)
        self.assertIn("HOLDOUT_VISIBILITY_UNVERIFIED", out.getvalue())

    def test_cli_invalid(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["validate-test", str(ROOT / "test_contracts/examples/invalid_missing_negative.yaml"), "--base-dir", str(FIXTURES)])
        self.assertEqual(code, 2)
        self.assertIn("BLOCKED_BEFORE_MODEL", out.getvalue())


if __name__ == "__main__":
    unittest.main()
