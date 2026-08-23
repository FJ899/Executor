from __future__ import annotations

import unittest

from executor.external_effect_receipt import assess_external_completion_claim


class ExternalEffectReceiptTests(unittest.TestCase):
    def setUp(self):
        self.expected = {
            "expected_provider": "GITHUB",
            "expected_action_kind": "CREATE_ISSUE_COMMENT",
            "expected_target": "eclipse-jdtls/eclipse.jdt.ls#3866",
        }
        self.receipt = {
            "schema_version": "executor-external-effect-receipt/1.0",
            "provider": "GITHUB",
            "action_kind": "CREATE_ISSUE_COMMENT",
            "target": "eclipse-jdtls/eclipse.jdt.ls#3866",
            "provider_status": 201,
            "object_id": "987654321",
            "object_url": "https://github.com/eclipse-jdtls/eclipse.jdt.ls/issues/3866#issuecomment-987654321",
            "response_sha256": "a" * 64,
        }

    def test_completion_claim_without_receipt_is_unverified(self):
        result = assess_external_completion_claim(
            claimed_status="ACTION_COMPLETED",
            receipt=None,
            **self.expected,
        )
        self.assertEqual(result["status"], "UNVERIFIED_EXTERNAL_EFFECT")
        self.assertEqual(result["reason"], "MISSING_AUTHORITATIVE_PROVIDER_RECEIPT")
        self.assertFalse(result["terminal_success"])

    def test_pass_claim_without_receipt_cannot_be_terminal_success(self):
        result = assess_external_completion_claim(
            claimed_status="PASS",
            receipt=None,
            **self.expected,
        )
        self.assertEqual(result["status"], "UNVERIFIED_EXTERNAL_EFFECT")
        self.assertFalse(result["terminal_success"])

    def test_human_supplied_permalink_is_not_a_provider_receipt(self):
        result = assess_external_completion_claim(
            claimed_status="ACTION_COMPLETED",
            receipt={
                "schema_version": "executor-external-effect-receipt/1.0",
                "provider": "GITHUB",
                "action_kind": "CREATE_ISSUE_COMMENT",
                "target": "eclipse-jdtls/eclipse.jdt.ls#3866",
                "object_id": "987654321",
                "object_url": self.receipt["object_url"],
            },
            **self.expected,
        )
        self.assertEqual(result["status"], "UNVERIFIED_EXTERNAL_EFFECT")
        self.assertEqual(result["reason"], "INVALID_AUTHORITATIVE_PROVIDER_RECEIPT")
        self.assertFalse(result["terminal_success"])

    def test_receipt_for_wrong_target_is_rejected(self):
        receipt = {**self.receipt, "target": "somewhere/else#1"}
        result = assess_external_completion_claim(
            claimed_status="ACTION_COMPLETED",
            receipt=receipt,
            **self.expected,
        )
        self.assertEqual(result["status"], "UNVERIFIED_EXTERNAL_EFFECT")
        self.assertIn("target mismatch", result["detail"])
        self.assertFalse(result["terminal_success"])

    def test_valid_provider_receipt_still_requires_independent_readback(self):
        result = assess_external_completion_claim(
            claimed_status="ACTION_COMPLETED",
            receipt=self.receipt,
            **self.expected,
        )
        self.assertEqual(result["status"], "RECEIPT_BOUND_VERIFICATION_REQUIRED")
        self.assertFalse(result["terminal_success"])
        self.assertEqual(result["receipt"]["object_id"], "987654321")


if __name__ == "__main__":
    unittest.main()
