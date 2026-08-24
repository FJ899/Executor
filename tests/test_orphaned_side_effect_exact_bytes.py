from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from executor.orphaned_side_effect import (
    _persist_external_effect_attempt,
    _persist_verified_external_recovery_scan,
    assess_orphaned_side_effect_recovery,
)


class OrphanedSideEffectExactBytesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.evidence_dir = Path(self.temp.name) / "evidence"
        self.provider = "GITHUB"
        self.action_kind = "CREATE_ISSUE_COMMENT"
        self.target = "fixture-owner/fixture-repo#123"
        self.effect_body = "  exact recovery body\n"
        self.effect_bytes = self.effect_body.encode("utf-8")
        self.effect_sha256 = hashlib.sha256(self.effect_bytes).hexdigest()
        with mock.patch(
            "executor.orphaned_side_effect.secrets.token_hex",
            return_value="fedcba9876543210fedcba9876543210",
        ):
            self.attempt = _persist_external_effect_attempt(
                provider=self.provider,
                action_kind=self.action_kind,
                target=self.target,
                effect_bytes=self.effect_bytes,
                started_at="2026-08-23T18:20:00Z",
                evidence_directory=self.evidence_dir,
            )
        self.attempt_id = self.attempt.attempt_id

    def _scan(self, body: str):
        response = json.dumps(
            {
                "complete": True,
                "objects": [
                    {
                        "id": 987654399,
                        "html_url": (
                            "https://github.com/fixture-owner/fixture-repo/issues/"
                            "123#issuecomment-987654399"
                        ),
                        "body": body,
                        "correlation_id": self.attempt_id,
                        "created_at": "2026-08-23T18:20:30Z",
                    }
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return _persist_verified_external_recovery_scan(
            scan_response=response,
            evidence_directory=self.evidence_dir,
            provider=self.provider,
            action_kind=self.action_kind,
            target=self.target,
            scanned_at="2026-08-23T18:21:00Z",
        )

    def _assess(self, scan):
        return assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=None,
            recovery_scan=scan,
            expected_provider=self.provider,
            expected_action_kind=self.action_kind,
            expected_target=self.target,
            expected_effect_sha256=self.effect_sha256,
        )

    def test_recovery_hash_preserves_leading_trailing_whitespace_and_newline(self):
        scan = self._scan(self.effect_body)
        self.assertEqual(scan.candidates[0].effect_sha256, self.effect_sha256)
        result = self._assess(scan)
        self.assertEqual(result["system_write"], "RECOVERED_EXTERNAL_EFFECT")
        self.assertEqual(result["effect_sha256"], self.effect_sha256)
        self.assertFalse(result["terminal_pass"])

    def test_trimmed_body_cannot_match_exact_attempt_effect(self):
        scan = self._scan(self.effect_body.strip())
        self.assertNotEqual(scan.candidates[0].effect_sha256, self.effect_sha256)
        result = self._assess(scan)
        self.assertEqual(result["system_write"], "RECOVERY_REQUIRED")
        self.assertEqual(
            result["recovery_status"], "NO_EXACT_CORRELATED_OBJECT_OBSERVED"
        )
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertFalse(result["terminal_pass"])


if __name__ == "__main__":
    unittest.main()
