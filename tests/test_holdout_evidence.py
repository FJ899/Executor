import hashlib
import unittest
from pathlib import Path

from executor.contracts import ValidationStatus, load_contract, validate_test_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


class HoldoutEvidenceTest(unittest.TestCase):
    def contract(self):
        return load_contract(ROOT / "test_contracts/examples/valid_test.yaml")

    def evidence(self, contract):
        location = contract["holdout"]["location"]
        payload = (FIXTURES / location).read_bytes()
        return {
            "schema_version": "executor-holdout-evidence/1.0",
            "attestation_id": "focused-test",
            "test_id": contract["test_id"],
            "location": location,
            "artifact_sha256": hashlib.sha256(payload).hexdigest(),
            "visibility": "HIDDEN_FROM_IMPLEMENTER",
            "access": "REPLAY_ONLY",
            "verifier_role": "TEST_FIXTURE_VERIFIER",
            "verifier": "focused-test-verifier",
        }

    def test_fixture_attestation_is_valid_only_in_fixture_namespace(self):
        contract = self.contract()
        result = validate_test_contract(contract, base_dir=FIXTURES, holdout_evidence=self.evidence(contract))
        self.assertEqual(result.status, ValidationStatus.VALID)

    def test_self_declared_independent_role_cannot_prove_hiddenness(self):
        contract = self.contract()
        contract["test_id"] = "GINSENG_TEST-003"
        evidence = self.evidence(self.contract())
        evidence["test_id"] = contract["test_id"]
        evidence["verifier_role"] = "INDEPENDENT_HOLDOUT_VERIFIER"
        result = validate_test_contract(contract, base_dir=FIXTURES, holdout_evidence=evidence)
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("INDEPENDENT_HOLDOUT_VERIFICATION_UNAVAILABLE", {issue.code for issue in result.issues})


if __name__ == "__main__":
    unittest.main()
