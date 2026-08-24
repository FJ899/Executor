from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from executor.external_effect_receipt import (
    ExternalEffectReceiptError,
    VerifiedExternalEffectReceipt,
    VerifiedExternalObservation,
    _persist_verified_external_observation,
    _persist_verified_system_write_receipt,
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
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.evidence_dir = Path(self.temp.name) / "evidence"

        target = self.fixture["target"]
        self.effect_bytes = target["effect_body"].encode("utf-8")
        self.expected = {
            "expected_provider": target["provider"],
            "expected_action_kind": target["action_kind"],
            "expected_target": target["resource"],
            "expected_effect_sha256": hashlib.sha256(self.effect_bytes).hexdigest(),
        }

        provider_event = self.fixture["events"][1]
        provider_response = provider_event["raw_response"].encode("utf-8")
        self.failure_receipt = _persist_verified_system_write_receipt(
            provider_response=provider_response,
            effect_bytes=self.effect_bytes,
            evidence_directory=self.evidence_dir,
            provider=target["provider"],
            action_kind=target["action_kind"],
            target=target["resource"],
            provider_status=provider_event["provider_status"],
            provider_message=provider_event["provider_message"],
        )

    def _success_receipt(
        self,
        *,
        target: str | None = None,
        object_id: str = "987654321",
        object_url: str | None = None,
        effect_bytes: bytes | None = None,
    ):
        target = target or self.expected["expected_target"]
        object_url = object_url or (
            "https://github.com/fixture-owner/fixture-repo/issues/"
            "123#issuecomment-987654321"
        )
        response = json.dumps(
            {
                "id": int(object_id),
                "html_url": object_url,
                "body": (effect_bytes or self.effect_bytes).decode("utf-8"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _persist_verified_system_write_receipt(
            provider_response=response,
            effect_bytes=effect_bytes or self.effect_bytes,
            evidence_directory=self.evidence_dir,
            provider="GITHUB",
            action_kind="CREATE_ISSUE_COMMENT",
            target=target,
            provider_status=201,
            provider_message="Created",
            object_id=object_id,
            object_url=object_url,
        )

    def _observation(
        self,
        *,
        target: str | None = None,
        object_id: str = "987654321",
        object_url: str | None = None,
        effect_bytes: bytes | None = None,
    ):
        target = target or self.expected["expected_target"]
        object_url = object_url or (
            "https://github.com/fixture-owner/fixture-repo/issues/"
            "123#issuecomment-987654321"
        )
        observed_effect = effect_bytes or self.effect_bytes
        response = json.dumps(
            {
                "id": int(object_id),
                "html_url": object_url,
                "body": observed_effect.decode("utf-8"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _persist_verified_external_observation(
            provider_response=response,
            observed_effect_bytes=observed_effect,
            evidence_directory=self.evidence_dir,
            provider="GITHUB",
            action_kind="CREATE_ISSUE_COMMENT",
            target=target,
            object_id=object_id,
            object_url=object_url,
            observed_at="2026-08-23T17:30:00Z",
        )

    def test_403_is_an_authoritative_failure_receipt(self):
        result = assess_system_write(
            receipt=self.failure_receipt,
            **self.expected,
        )
        expected = self.fixture["expected"]
        self.assertEqual(result["system_write"], "FAILED")
        self.assertEqual(
            result["system_receipt"], "AUTHORITATIVE_FAILURE_RECEIPT"
        )
        self.assertEqual(result["receipt"].provider_status, 403)
        self.assertEqual(
            result["receipt"].provider_message,
            "Resource not accessible by integration",
        )
        self.assertIsNone(result["receipt"].object_id)
        self.assertIsNone(result["receipt"].object_url)
        self.assertEqual(
            result["receipt"].response_sha256,
            expected["system_response_sha256"],
        )
        self.assertEqual(
            result["receipt"].effect_sha256,
            expected["effect_sha256"],
        )
        self.assertTrue(Path(result["receipt"].receipt_ref).is_file())
        self.assertFalse(result["system_completion"])
        self.assertFalse(result["terminal_pass"])

    def test_fixture_flow_stays_human_reported_unverified(self):
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_observation=None,
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
        self.assertEqual(result["observation_status"], "MISSING")

    def test_human_claim_never_inherits_system_completed(self):
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_observation=None,
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
        self.assertFalse(result["terminal_pass"])
        self.assertEqual(
            result["reason"], "NO_RECEIPT_NO_SYSTEM_COMPLETION_CLAIM"
        )

    def test_raw_dictionary_cannot_be_used_as_authoritative_receipt(self):
        forged = {
            "provider": "GITHUB",
            "provider_status": 201,
            "object_id": "987654321",
            "object_url": (
                "https://github.com/fixture-owner/fixture-repo/issues/"
                "123#issuecomment-987654321"
            ),
        }
        result = assess_system_write(receipt=forged, **self.expected)
        self.assertEqual(result["system_write"], "UNVERIFIED")
        self.assertEqual(result["system_receipt"], "INVALID")
        self.assertIn("VerifiedExternalEffectReceipt", result["detail"])
        self.assertFalse(result["system_completion"])
        self.assertFalse(result["terminal_pass"])

    def test_verified_receipt_cannot_be_constructed_or_replaced_by_caller(self):
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "trusted provider gateway"
        ):
            VerifiedExternalEffectReceipt(
                provider="GITHUB",
                actor="SYSTEM",
                action_kind="CREATE_ISSUE_COMMENT",
                target="fixture-owner/fixture-repo#123",
                provider_status=201,
                provider_message="Created",
                object_id="987654321",
                object_url=(
                    "https://github.com/fixture-owner/fixture-repo/issues/"
                    "123#issuecomment-987654321"
                ),
                response_sha256="a" * 64,
                effect_sha256=self.expected["expected_effect_sha256"],
                provider_outcome="SUCCESS",
                receipt_ref="/tmp/fake.json",
                evidence_sha256="b" * 64,
            )

        legitimate = self._success_receipt()
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "trusted provider gateway"
        ):
            replace(legitimate, target="other/repo#999")

    def test_success_requires_durable_object_identity(self):
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "durable provider object identity"
        ):
            _persist_verified_system_write_receipt(
                provider_response=b'{"created":true}',
                effect_bytes=self.effect_bytes,
                evidence_directory=self.evidence_dir,
                provider="GITHUB",
                action_kind="CREATE_ISSUE_COMMENT",
                target="fixture-owner/fixture-repo#123",
                provider_status=201,
                provider_message="Created",
            )

    def test_success_identity_must_bind_exact_target_and_comment_id(self):
        cases = [
            (
                "https://example.com/fixture-owner/fixture-repo/issues/"
                "123#issuecomment-987654321",
                "987654321",
            ),
            (
                "https://github.com/fixture-owner/other/issues/"
                "123#issuecomment-987654321",
                "987654321",
            ),
            (
                "https://github.com/fixture-owner/fixture-repo/issues/"
                "124#issuecomment-987654321",
                "987654321",
            ),
            (
                "https://github.com/fixture-owner/fixture-repo/issues/"
                "123#issuecomment-111",
                "987654321",
            ),
        ]
        for object_url, object_id in cases:
            with self.subTest(object_url=object_url), self.assertRaisesRegex(
                ExternalEffectReceiptError, "not bound to the expected target"
            ):
                self._success_receipt(
                    object_url=object_url,
                    object_id=object_id,
                )

    def test_valid_success_receipt_is_persisted_before_system_completion(self):
        receipt = self._success_receipt()
        result = assess_system_write(receipt=receipt, **self.expected)
        self.assertEqual(result["system_write"], "COMPLETED")
        self.assertEqual(
            result["system_receipt"], "AUTHORITATIVE_SUCCESS_RECEIPT"
        )
        self.assertTrue(result["system_completion"])
        self.assertEqual(result["verification"], "INDEPENDENT_READ_REQUIRED")
        self.assertTrue(Path(receipt.receipt_ref).is_file())
        self.assertFalse(result["terminal_pass"])

    def test_missing_or_tampered_persistence_invalidates_completion(self):
        receipt = self._success_receipt()
        evidence = Path(receipt.receipt_ref)
        evidence.write_text('{"tampered":true}\n', encoding="utf-8")
        result = assess_system_write(receipt=receipt, **self.expected)
        self.assertEqual(result["system_write"], "UNVERIFIED")
        self.assertEqual(result["system_receipt"], "INVALID")
        self.assertFalse(result["system_completion"])
        self.assertFalse(result["terminal_pass"])
        self.assertIn("hash mismatch", result["detail"])

    def test_response_sha_is_computed_from_actual_provider_response_bytes(self):
        raw = b'{"message":"Created","id":987654321}'
        receipt = _persist_verified_system_write_receipt(
            provider_response=raw,
            effect_bytes=self.effect_bytes,
            evidence_directory=self.evidence_dir,
            provider="GITHUB",
            action_kind="CREATE_ISSUE_COMMENT",
            target="fixture-owner/fixture-repo#123",
            provider_status=201,
            provider_message="Created",
            object_id="987654321",
            object_url=(
                "https://github.com/fixture-owner/fixture-repo/issues/"
                "123#issuecomment-987654321"
            ),
        )
        self.assertEqual(receipt.response_sha256, hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(receipt.response_sha256, "a" * 64)

    def test_valid_independent_observation_marks_human_event_observed_only(self):
        observation = self._observation()
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_observation=observation,
            **self.expected,
        )
        self.assertEqual(result["system"]["system_write"], "FAILED")
        self.assertEqual(result["human_write"], "HUMAN_REPORTED")
        self.assertEqual(result["human_verification"], "OBSERVED")
        self.assertEqual(result["observation_status"], "VERIFIED")
        self.assertTrue(result["evidence_non_substitution"])
        self.assertFalse(result["terminal_pass"])

    def test_observation_of_wrong_target_cannot_verify_human_claim(self):
        observation = self._observation(
            target="fixture-owner/fixture-repo#124",
            object_url=(
                "https://github.com/fixture-owner/fixture-repo/issues/"
                "124#issuecomment-987654321"
            ),
        )
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_observation=observation,
            **self.expected,
        )
        self.assertEqual(result["human_verification"], "UNVERIFIED")
        self.assertEqual(result["observation_status"], "INVALID")
        self.assertIn("target mismatch", result["observation_detail"])
        self.assertFalse(result["terminal_pass"])

    def test_observation_of_wrong_effect_cannot_verify_human_claim(self):
        observation = self._observation(effect_bytes=b"different comment body")
        result = assess_actor_receipt_provenance(
            system_receipt=self.failure_receipt,
            human_write_claim=True,
            independent_observation=observation,
            **self.expected,
        )
        self.assertEqual(result["human_verification"], "UNVERIFIED")
        self.assertEqual(result["observation_status"], "INVALID")
        self.assertIn("effect fingerprint mismatch", result["observation_detail"])

    def test_boolean_shortcuts_are_rejected(self):
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "human_write_claim must be a boolean"
        ):
            assess_actor_receipt_provenance(
                system_receipt=self.failure_receipt,
                human_write_claim="false",
                independent_observation=None,
                **self.expected,
            )

        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "VerifiedExternalObservation"
        ):
            assess_actor_receipt_provenance(
                system_receipt=self.failure_receipt,
                human_write_claim=True,
                independent_observation="false",
                **self.expected,
            )

    def test_verified_observation_cannot_be_constructed_by_caller(self):
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "trusted verifier gateway"
        ):
            VerifiedExternalObservation(
                provider="GITHUB",
                action_kind="CREATE_ISSUE_COMMENT",
                target="fixture-owner/fixture-repo#123",
                object_id="987654321",
                object_url=(
                    "https://github.com/fixture-owner/fixture-repo/issues/"
                    "123#issuecomment-987654321"
                ),
                effect_sha256=self.expected["expected_effect_sha256"],
                observed_at="2026-08-23T17:30:00Z",
                response_sha256="a" * 64,
                observation_ref="/tmp/fake.json",
                evidence_sha256="b" * 64,
            )


if __name__ == "__main__":
    unittest.main()
