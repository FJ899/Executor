from __future__ import annotations

import json
import unittest
from pathlib import Path

from executor.external_effect_receipt import (
    assess_actor_receipt_provenance,
    assess_system_write,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "actor_receipt_provenance"
    / "ARP_001_SYSTEM_403_HUMAN_CLAIM_UNOBSERVED.json"
)


class ActorReceiptProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        target = self.fixture["target"]
        self.expected = {
            "expected_provider": target["provider"],
            "expected_action_kind": target["action_kind"],
            "expected_target": target["resource"],
        }
        self.failure_receipt = self.fixture["events"][1]["receipt"]

    def test_403_is_an_authoritative_failure_receipt(self):
        result = assess_system_write(
            receipt=self.failure_receipt,
            **self.expected,
        )
        self.assertEqual(result["system_write"], "FAILED")
        self.assertEqual(
            result["system_receipt"], "AUTHORITATIVE_FAILURE_RECEIPT"
        )
        self.assertEqual(result["receipt"]["provider_status"], 403)
        self.assertEqual(
            result["receipt"]["provider_message"],
            "Resource not accessible by integration",
        )
        self.assertIsNone(result["receipt"]["object_id"])
        self.assertIsNone(result["receipt"]["object_url"])
        self.assertFalse(result["system_completion"])
        self.assertFalse(result["terminal_success"])

    def test_fixture_flow_stays_human_reported_unverified(self):
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_read_observed=False,
            **self.expected,
        )
        expected = self.fixture["expected"]
        self.assertEqual(result["system"]["system_write"], expected["system_write"])
        self.assertEqual(
            result["system"]["system_receipt"], expected["system_receipt"]
        )
        self.assertEqual(result["human_write"], expected["human_write"])
        self.assertEqual(
            result["human_verification"], expected["human_verification"]
        )
        self.assertEqual(result["current_result"], expected["current_result"])
        self.assertEqual(result["terminal_pass"], expected["terminal_pass"])

    def test_human_claim_never_inherits_system_completed(self):
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_read_observed=False,
            **self.expected,
        )
        self.assertEqual(result["system"]["system_write"], "FAILED")
        self.assertEqual(result["current_result"], "HUMAN_REPORTED / UNVERIFIED")
        self.assertNotEqual(result["current_result"], "SYSTEM_COMPLETED")
        self.assertEqual(
            result["provenance_rule"],
            "HUMAN_CLAIM_MUST_NOT_INHERIT_SYSTEM_COMPLETION",
        )

    def test_missing_system_receipt_cannot_support_system_completion(self):
        result = assess_system_write(receipt=None, **self.expected)
        self.assertEqual(result["system_write"], "UNVERIFIED")
        self.assertEqual(result["system_receipt"], "MISSING")
        self.assertFalse(result["system_completion"])
        self.assertEqual(
            result["reason"], "NO_RECEIPT_NO_SYSTEM_COMPLETION_CLAIM"
        )

    def test_success_receipt_requires_durable_object_identity(self):
        invalid_success = {
            **self.failure_receipt,
            "provider_status": 201,
            "provider_message": "Created",
        }
        result = assess_system_write(receipt=invalid_success, **self.expected)
        self.assertEqual(result["system_write"], "UNVERIFIED")
        self.assertEqual(result["system_receipt"], "INVALID")
        self.assertIn("durable provider object identity", result["detail"])
        self.assertFalse(result["terminal_success"])

    def test_valid_success_receipt_completes_system_write_but_not_terminal_pass(self):
        valid_success = {
            **self.failure_receipt,
            "provider_status": 201,
            "provider_message": "Created",
            "object_id": "987654321",
            "object_url": "https://github.com/fixture-owner/fixture-repo/issues/123#issuecomment-987654321",
        }
        result = assess_system_write(receipt=valid_success, **self.expected)
        self.assertEqual(result["system_write"], "COMPLETED")
        self.assertEqual(
            result["system_receipt"], "AUTHORITATIVE_SUCCESS_RECEIPT"
        )
        self.assertTrue(result["system_completion"])
        self.assertEqual(result["verification"], "INDEPENDENT_READ_REQUIRED")
        self.assertFalse(result["terminal_success"])

    def test_independent_observation_of_human_claim_does_not_rewrite_system_history(self):
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_read_observed=True,
            **self.expected,
        )
        self.assertEqual(result["system"]["system_write"], "FAILED")
        self.assertEqual(result["human_write"], "HUMAN_REPORTED")
        self.assertEqual(result["human_verification"], "OBSERVED")
        self.assertTrue(result["evidence_non_substitution"])
        self.assertFalse(result["terminal_pass"])


if __name__ == "__main__":
    unittest.main()
