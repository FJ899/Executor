import unittest
from pathlib import Path

from executor.contracts import ValidationStatus, load_contract, validate_test_contract


ROOT = Path(__file__).resolve().parents[1]


class M3ContractFreezeTest(unittest.TestCase):
    def test_self_test_contract_is_frozen_but_cannot_claim_readiness_before_m3(self):
        contract = load_contract(ROOT / "test_contracts/EXECUTOR_SELF_TEST-001.yaml")
        result = validate_test_contract(
            contract,
            base_dir=ROOT / "tests/fixtures",
        )
        self.assertEqual(result.status, ValidationStatus.INSUFFICIENT_EVIDENCE)
        self.assertIn("HOLDOUT_NOT_FOUND", {issue.code for issue in result.issues})

    def test_contract_names_all_terminal_m3_bindings(self):
        text = (ROOT / "M3_REPLAYABLE_EVIDENCE_CONTRACT_v1.0.md").read_text(
            encoding="utf-8"
        )
        for required in (
            "M3A — independent holdout replay",
            "M3B — atomic Action Authorization Packet consumption",
            "M3C — replayable evidence and terminal PASS",
            "EXECUTOR_SELF_TEST-001",
            "concurrent",
            "result-binding token",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
