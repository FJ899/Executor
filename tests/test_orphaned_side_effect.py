from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from executor.external_effect_receipt import ExternalEffectReceiptError
from executor.orphaned_side_effect import (
    OrphanedSideEffectRecoveryRequired,
    VerifiedExternalEffectAttempt,
    VerifiedExternalRecoveryScan,
    _persist_external_effect_attempt,
    _persist_provider_result_for_attempt,
    _persist_verified_external_recovery_scan,
    assess_orphaned_side_effect_recovery,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "orphaned_side_effect"
    / "OSE_001_PROVIDER_SUCCESS_CRASH_BEFORE_RECEIPT.json"
)


class OrphanedSideEffectTests(unittest.TestCase):
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
        minted = target["expected_minted_attempt_id"]
        with mock.patch(
            "executor.orphaned_side_effect.secrets.token_hex",
            return_value=minted.removeprefix("ose-"),
        ):
            self.attempt = _persist_external_effect_attempt(
                provider=target["provider"],
                action_kind=target["action_kind"],
                target=target["resource"],
                effect_bytes=self.effect_bytes,
                started_at=target["started_at"],
                evidence_directory=self.evidence_dir,
            )
        self.assertEqual(self.attempt.attempt_id, minted)

    def _scan(self, name: str):
        payload = json.loads(json.dumps(self.fixture["recovery_scans"][name]))
        expected_fixture_id = self.fixture["target"]["expected_minted_attempt_id"]
        for item in payload["objects"]:
            if item["correlation_id"] == expected_fixture_id:
                item["correlation_id"] = self.attempt.attempt_id
        response = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _persist_verified_external_recovery_scan(
            scan_response=response,
            evidence_directory=self.evidence_dir,
            provider=self.expected["expected_provider"],
            action_kind=self.expected["expected_action_kind"],
            target=self.expected["expected_target"],
            scanned_at="2026-08-23T18:11:00Z",
        )

    def _success_receipt(self):
        event = self.fixture["events"][1]
        response = json.dumps(
            {
                "id": int(event["object_id"]),
                "html_url": event["object_url"],
                "body": self.fixture["target"]["effect_body"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _persist_provider_result_for_attempt(
            attempt=self.attempt,
            provider_response=response,
            effect_bytes=self.effect_bytes,
            evidence_directory=self.evidence_dir,
            provider_status=event["provider_status"],
            provider_message=event["provider_message"],
            object_id=event["object_id"],
            object_url=event["object_url"],
        )

    def test_pre_write_attempt_is_durable_and_retry_forbidden(self):
        self.assertEqual(self.attempt.attempt_state, "WRITE_IN_FLIGHT")
        self.assertEqual(
            self.attempt.retry_policy,
            "FORBIDDEN_WHILE_UNRESOLVED",
        )
        self.assertEqual(
            self.attempt.effect_sha256,
            self.expected["expected_effect_sha256"],
        )
        self.assertTrue(Path(self.attempt.attempt_ref).is_file())

    def test_missing_receipt_after_inflight_attempt_is_recovery_required(self):
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=None,
            **self.expected,
        )
        expected = self.fixture["expected_before_recovery"]
        self.assertEqual(result["system_write"], expected["system_write"])
        self.assertEqual(
            result["external_effect_state"], expected["external_effect_state"]
        )
        self.assertEqual(result["system_completion"], expected["system_completion"])
        self.assertEqual(
            result["automatic_retry_allowed"], expected["automatic_retry_allowed"]
        )
        self.assertEqual(result["terminal_pass"], expected["terminal_pass"])
        self.assertEqual(
            result["recovery_status"],
            "AUTHORITATIVE_PROVIDER_RECONCILIATION_REQUIRED",
        )

    def test_provider_success_persistence_failure_is_not_clean_failure(self):
        event = self.fixture["events"][1]
        with mock.patch(
            "executor.orphaned_side_effect._persist_verified_system_write_receipt",
            side_effect=OSError("synthetic crash window"),
        ):
            with self.assertRaisesRegex(
                OrphanedSideEffectRecoveryRequired,
                "requires reconciliation and must not be retried",
            ):
                _persist_provider_result_for_attempt(
                    attempt=self.attempt,
                    provider_response=b'{"id":987654321}',
                    effect_bytes=self.effect_bytes,
                    evidence_directory=self.evidence_dir,
                    provider_status=event["provider_status"],
                    provider_message=event["provider_message"],
                    object_id=event["object_id"],
                    object_url=event["object_url"],
                )

    def test_exact_complete_correlated_scan_recovers_object_without_fabricating_receipt(self):
        scan = self._scan("exact")
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=scan,
            **self.expected,
        )
        expected = self.fixture["expected_after_exact_recovery"]
        self.assertEqual(result["system_write"], expected["system_write"])
        self.assertEqual(
            result["external_effect_state"], expected["external_effect_state"]
        )
        self.assertEqual(
            result["original_success_receipt"],
            expected["original_success_receipt"],
        )
        self.assertFalse(result["system_completion"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])
        self.assertEqual(result["recovery_status"], expected["recovery_status"])
        self.assertEqual(result["next_gate"], expected["next_gate"])
        self.assertEqual(result["object_id"], "987654321")
        self.assertEqual(result["created_at"], "2026-08-23T18:10:30Z")
        self.assertEqual(
            result["provenance_rule"],
            "RECOVERY_DOES_NOT_FABRICATE_ORIGINAL_SUCCESS_RECEIPT",
        )

    def test_same_effect_without_attempt_correlation_is_not_recovery_proof(self):
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=self._scan("same_effect_without_correlation"),
            **self.expected,
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(
            result["recovery_status"], "NO_EXACT_CORRELATED_OBJECT_OBSERVED"
        )
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])

    def test_incomplete_scan_cannot_resolve_even_with_exact_match(self):
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=self._scan("incomplete_exact"),
            **self.expected,
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "RECOVERY_SCAN_INCOMPLETE")
        self.assertFalse(result["automatic_retry_allowed"])

    def test_multiple_exact_matches_are_ambiguous(self):
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=self._scan("ambiguous"),
            **self.expected,
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "AMBIGUOUS_CORRELATED_OBJECTS")
        self.assertFalse(result["automatic_retry_allowed"])

    def test_zero_match_does_not_downgrade_unknown_post_write_to_clean_failure(self):
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=self._scan("none"),
            **self.expected,
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["external_effect_state"], "POSSIBLY_CREATED")
        self.assertEqual(
            result["recovery_status"], "NO_EXACT_CORRELATED_OBJECT_OBSERVED"
        )
        self.assertNotEqual(result["system_write"], "FAILED")
        self.assertFalse(result["automatic_retry_allowed"])

    def test_authoritative_success_receipt_closes_orphan_path_normally(self):
        receipt = self._success_receipt()
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=receipt,
            recovery_scan=None,
            **self.expected,
        )
        self.assertEqual(result["system_write"], "COMPLETED")
        self.assertEqual(result["orphaned_side_effect"], "NOT_ACTIVE")
        self.assertEqual(
            result["recovery_status"],
            "NOT_REQUIRED_AUTHORITATIVE_RECEIPT_PRESENT",
        )
        self.assertEqual(result["provider_result_disposition"], "SUCCESS")
        self.assertTrue(result["system_completion"])
        self.assertFalse(result["terminal_pass"])

    def test_attempt_tamper_fails_closed_and_never_enables_retry(self):
        Path(self.attempt.attempt_ref).write_text(
            '{"tampered":true}\n', encoding="utf-8"
        )
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=None,
            **self.expected,
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "ATTEMPT_EVIDENCE_INVALID")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])

    def test_wrong_target_recovery_scan_is_rejected(self):
        response = json.dumps(
            {
                "complete": True,
                "objects": [
                    {
                        "id": 987654321,
                        "html_url": (
                            "https://github.com/fixture-owner/fixture-repo/issues/"
                            "124#issuecomment-987654321"
                        ),
                        "body": self.fixture["target"]["effect_body"],
                        "correlation_id": self.attempt.attempt_id,
                        "created_at": "2026-08-23T18:10:30Z",
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        scan = _persist_verified_external_recovery_scan(
            scan_response=response,
            evidence_directory=self.evidence_dir,
            provider="GITHUB",
            action_kind="CREATE_ISSUE_COMMENT",
            target="fixture-owner/fixture-repo#124",
            scanned_at="2026-08-23T18:11:00Z",
        )
        result = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=scan,
            **self.expected,
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "RECOVERY_SCAN_INVALID")
        self.assertIn("target mismatch", result["detail"])

    def test_scan_complete_truthy_string_is_rejected(self):
        response = json.dumps(
            {"complete": "true", "objects": []},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "complete must be a boolean"
        ):
            _persist_verified_external_recovery_scan(
                scan_response=response,
                evidence_directory=self.evidence_dir,
                provider="GITHUB",
                action_kind="CREATE_ISSUE_COMMENT",
                target="fixture-owner/fixture-repo#123",
                scanned_at="2026-08-23T18:11:00Z",
            )

    def test_recovery_scan_is_derived_from_persisted_scan_bytes(self):
        payload = json.loads(json.dumps(self.fixture["recovery_scans"]["exact"]))
        payload["objects"][0]["correlation_id"] = self.attempt.attempt_id
        response = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        scan = _persist_verified_external_recovery_scan(
            scan_response=response,
            evidence_directory=self.evidence_dir,
            provider="GITHUB",
            action_kind="CREATE_ISSUE_COMMENT",
            target="fixture-owner/fixture-repo#123",
            scanned_at="2026-08-23T18:11:00Z",
        )
        self.assertEqual(scan.response_sha256, hashlib.sha256(response).hexdigest())
        self.assertEqual(
            scan.candidates[0].effect_sha256,
            self.expected["expected_effect_sha256"],
        )
        self.assertEqual(scan.candidates[0].created_at, "2026-08-23T18:10:30Z")
        self.assertTrue(Path(scan.scan_ref).is_file())

    def test_verified_recovery_objects_cannot_be_constructed_or_replaced_by_caller(self):
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "must be minted before the provider write"
        ):
            VerifiedExternalEffectAttempt(
                provider="GITHUB",
                action_kind="CREATE_ISSUE_COMMENT",
                target="fixture-owner/fixture-repo#123",
                attempt_id="ose-0123456789abcdef0123456789abcdef",
                effect_sha256=self.expected["expected_effect_sha256"],
                started_at="2026-08-23T18:10:00Z",
                attempt_state="WRITE_IN_FLIGHT",
                retry_policy="FORBIDDEN_WHILE_UNRESOLVED",
                attempt_ref="/tmp/fake.json",
                evidence_sha256="a" * 64,
            )

        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "trusted recovery verifier"
        ):
            VerifiedExternalRecoveryScan(
                provider="GITHUB",
                action_kind="CREATE_ISSUE_COMMENT",
                target="fixture-owner/fixture-repo#123",
                scanned_at="2026-08-23T18:11:00Z",
                complete=True,
                candidates=(),
                response_sha256="a" * 64,
                scan_ref="/tmp/fake.json",
                evidence_sha256="b" * 64,
            )

        scan = self._scan("exact")
        with self.assertRaisesRegex(
            ExternalEffectReceiptError, "trusted recovery verifier"
        ):
            replace(scan, complete=False)


if __name__ == "__main__":
    unittest.main()
