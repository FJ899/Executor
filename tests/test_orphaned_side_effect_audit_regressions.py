from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from executor.external_effect_receipt import (
    ExternalEffectReceiptError,
    _persist_verified_system_write_receipt,
)
from executor.orphaned_side_effect import (
    OrphanedSideEffectRecoveryRequired,
    _persist_external_effect_attempt,
    _persist_provider_result_for_attempt,
    _persist_verified_external_recovery_scan,
    assess_orphaned_side_effect_recovery,
)


class OrphanedSideEffectAuditRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.evidence_dir = Path(self.temp.name) / "evidence"
        self.provider = "GITHUB"
        self.action_kind = "CREATE_ISSUE_COMMENT"
        self.target = "fixture-owner/fixture-repo#123"
        self.effect_bytes = b"OSE-001 exact attempted effect"
        self.effect_sha256 = hashlib.sha256(self.effect_bytes).hexdigest()

    def _attempt(self, nonce_hex: str):
        with mock.patch(
            "executor.orphaned_side_effect.secrets.token_hex", return_value=nonce_hex
        ):
            return _persist_external_effect_attempt(
                provider=self.provider,
                action_kind=self.action_kind,
                target=self.target,
                effect_bytes=self.effect_bytes,
                started_at="2026-08-23T18:30:00Z",
                evidence_directory=self.evidence_dir,
            )

    def _expected(self):
        return {
            "expected_provider": self.provider,
            "expected_action_kind": self.action_kind,
            "expected_target": self.target,
            "expected_effect_sha256": self.effect_sha256,
        }

    def _success_for(self, attempt, object_id: int = 987654500, evidence_dir=None):
        object_url = (
            "https://github.com/fixture-owner/fixture-repo/issues/"
            f"123#issuecomment-{object_id}"
        )
        response = json.dumps(
            {
                "id": object_id,
                "html_url": object_url,
                "body": self.effect_bytes.decode("utf-8"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _persist_provider_result_for_attempt(
            attempt=attempt,
            provider_response=response,
            effect_bytes=self.effect_bytes,
            evidence_directory=evidence_dir or self.evidence_dir,
            provider_status=201,
            provider_message="Created",
            object_id=str(object_id),
            object_url=object_url,
        )

    def _failure_for(self, attempt, *, status: int = 403, message: str = "Forbidden", evidence_dir=None):
        return _persist_provider_result_for_attempt(
            attempt=attempt,
            provider_response=json.dumps({"message": message}).encode("utf-8"),
            effect_bytes=self.effect_bytes,
            evidence_directory=evidence_dir or self.evidence_dir,
            provider_status=status,
            provider_message=message,
        )

    def _scan(self, objects, *, evidence_dir=None):
        normalized = []
        for obj in objects:
            item = dict(obj)
            item.setdefault("created_at", "2026-08-23T18:30:30Z")
            normalized.append(item)
        response = json.dumps(
            {"complete": True, "objects": normalized},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _persist_verified_external_recovery_scan(
            scan_response=response,
            evidence_directory=evidence_dir or self.evidence_dir,
            provider=self.provider,
            action_kind=self.action_kind,
            target=self.target,
            scanned_at="2026-08-23T18:31:00Z",
        )

    def test_success_receipt_from_attempt_a_cannot_complete_attempt_b(self):
        attempt_a = self._attempt("a" * 32)
        bound_a = self._success_for(attempt_a)
        attempt_b = self._attempt("b" * 32)
        result = assess_orphaned_side_effect_recovery(
            attempt=attempt_b,
            system_receipt=bound_a,
            recovery_scan=None,
            **self._expected(),
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "SYSTEM_RECEIPT_NOT_BOUND_TO_ATTEMPT")
        self.assertFalse(result["system_completion"])
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])

    def test_failure_receipt_from_attempt_a_cannot_fail_attempt_b(self):
        attempt_a = self._attempt("1" * 32)
        bound_a = self._failure_for(attempt_a)
        attempt_b = self._attempt("2" * 32)
        result = assess_orphaned_side_effect_recovery(
            attempt=attempt_b,
            system_receipt=bound_a,
            recovery_scan=None,
            **self._expected(),
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertNotEqual(result["system_write"], "FAILED")
        self.assertEqual(result["recovery_status"], "SYSTEM_RECEIPT_NOT_BOUND_TO_ATTEMPT")
        self.assertFalse(result["automatic_retry_allowed"])

    def test_raw_arp_receipt_without_attempt_binding_cannot_close_orphan(self):
        attempt = self._attempt("3" * 32)
        object_id = "987654501"
        object_url = (
            "https://github.com/fixture-owner/fixture-repo/issues/"
            f"123#issuecomment-{object_id}"
        )
        raw_receipt = _persist_verified_system_write_receipt(
            provider_response=b'{"id":987654501}',
            effect_bytes=self.effect_bytes,
            evidence_directory=self.evidence_dir,
            provider=self.provider,
            action_kind=self.action_kind,
            target=self.target,
            provider_status=201,
            provider_message="Created",
            object_id=object_id,
            object_url=object_url,
        )
        result = assess_orphaned_side_effect_recovery(
            attempt=attempt,
            system_receipt=raw_receipt,  # type: ignore[arg-type]
            recovery_scan=None,
            **self._expected(),
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "SYSTEM_RECEIPT_NOT_BOUND_TO_ATTEMPT")
        self.assertFalse(result["terminal_pass"])

    def test_attempt_id_is_minted_inside_boundary_and_reuse_is_atomically_rejected(self):
        nonce = "4" * 32
        first = self._attempt(nonce)
        self.assertEqual(first.attempt_id, f"ose-{nonce}")
        self.assertTrue(Path(first.attempt_ref).is_file())
        with self.assertRaisesRegex(ExternalEffectReceiptError, "attempt_id already reserved"):
            self._attempt(nonce)

    def test_correlation_id_collision_is_ambiguous_even_if_only_one_body_matches(self):
        attempt = self._attempt("5" * 32)
        correlation = attempt.attempt_id
        scan = self._scan(
            [
                {
                    "id": 987654510,
                    "html_url": "https://github.com/fixture-owner/fixture-repo/issues/123#issuecomment-987654510",
                    "body": self.effect_bytes.decode("utf-8"),
                    "correlation_id": correlation,
                },
                {
                    "id": 987654511,
                    "html_url": "https://github.com/fixture-owner/fixture-repo/issues/123#issuecomment-987654511",
                    "body": "different body",
                    "correlation_id": correlation,
                },
            ]
        )
        result = assess_orphaned_side_effect_recovery(
            attempt=attempt,
            system_receipt=None,
            recovery_scan=scan,
            **self._expected(),
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "AMBIGUOUS_CORRELATED_OBJECTS")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])

    def test_fresh_evidence_directory_is_fsynced_with_parent_before_attempt_returns(self):
        module = __import__("executor.orphaned_side_effect", fromlist=["_fsync_directory"])
        real_fsync_directory = module._fsync_directory
        with mock.patch(
            "executor.orphaned_side_effect._fsync_directory",
            wraps=real_fsync_directory,
        ) as fsync_directory:
            attempt = self._attempt("6" * 32)
        self.assertTrue(Path(attempt.attempt_ref).is_file())
        called_paths = [Path(call.args[0]).resolve() for call in fsync_directory.call_args_list]
        self.assertIn(self.evidence_dir.resolve(), called_paths)
        self.assertIn(self.evidence_dir.parent.resolve(), called_paths)

    def test_attempt_reservation_survives_as_unique_identity_file(self):
        nonce = "7" * 32
        attempt = self._attempt(nonce)
        path = Path(attempt.attempt_ref)
        self.assertEqual(path.name, f"external_effect_attempt-ose-{nonce}.json")
        self.assertTrue(path.is_file())
        self.assertEqual(len(attempt.evidence_sha256), 64)

    def test_conflicting_results_for_same_attempt_are_fail_closed(self):
        attempt = self._attempt("8" * 32)
        first = self._failure_for(attempt)
        first_result = assess_orphaned_side_effect_recovery(
            attempt=attempt,
            system_receipt=first,
            recovery_scan=None,
            **self._expected(),
        )
        self.assertEqual(first_result["system_write"], "FAILED")
        self.assertEqual(first_result["provider_result_disposition"], "DEFINITIVE_FAILURE")

        with self.assertRaisesRegex(
            OrphanedSideEffectRecoveryRequired,
            "requires reconciliation and must not be retried",
        ):
            self._success_for(attempt, object_id=987654520)

        result_slot = self.evidence_dir / f"external_effect_attempt_result-{attempt.attempt_id}.json"
        self.assertTrue(result_slot.is_file())

    def test_5xx_receipt_is_ambiguous_not_clean_failure(self):
        attempt = self._attempt("9" * 32)
        bound = self._failure_for(attempt, status=503, message="Service Unavailable")
        result = assess_orphaned_side_effect_recovery(
            attempt=attempt,
            system_receipt=bound,
            recovery_scan=None,
            **self._expected(),
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "AMBIGUOUS_PROVIDER_RESULT")
        self.assertEqual(result["provider_result_disposition"], "AMBIGUOUS")
        self.assertEqual(
            result["system_receipt_assessment"]["system_write"],
            "AMBIGUOUS_PROVIDER_RESULT",
        )
        self.assertEqual(
            result["system_receipt_assessment"]["arp_system_write"], "FAILED"
        )
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])

    def test_preexisting_correlated_object_cannot_be_recovered_as_new_attempt(self):
        attempt = self._attempt("a1" * 16)
        scan = self._scan(
            [
                {
                    "id": 987654530,
                    "html_url": "https://github.com/fixture-owner/fixture-repo/issues/123#issuecomment-987654530",
                    "body": self.effect_bytes.decode("utf-8"),
                    "correlation_id": attempt.attempt_id,
                    "created_at": "2026-08-23T18:29:59Z",
                }
            ]
        )
        result = assess_orphaned_side_effect_recovery(
            attempt=attempt,
            system_receipt=None,
            recovery_scan=scan,
            **self._expected(),
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "CORRELATED_OBJECT_PREEXISTS_ATTEMPT")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])

    def test_cross_root_result_binding_is_rejected(self):
        attempt = self._attempt("b1" * 16)
        other_root = Path(self.temp.name) / "other-evidence"
        other_root.mkdir()
        with self.assertRaisesRegex(
            OrphanedSideEffectRecoveryRequired,
            "requires reconciliation and must not be retried",
        ):
            self._failure_for(attempt, evidence_dir=other_root)

    def test_cross_root_recovery_scan_is_rejected(self):
        attempt = self._attempt("c1" * 16)
        other_root = Path(self.temp.name) / "other-scan-evidence"
        other_root.mkdir()
        scan = self._scan(
            [
                {
                    "id": 987654540,
                    "html_url": "https://github.com/fixture-owner/fixture-repo/issues/123#issuecomment-987654540",
                    "body": self.effect_bytes.decode("utf-8"),
                    "correlation_id": attempt.attempt_id,
                }
            ],
            evidence_dir=other_root,
        )
        result = assess_orphaned_side_effect_recovery(
            attempt=attempt,
            system_receipt=None,
            recovery_scan=scan,
            **self._expected(),
        )
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(result["recovery_status"], "RECOVERY_SCAN_INVALID")
        self.assertIn("attempt evidence root", result["detail"])


if __name__ == "__main__":
    unittest.main()
