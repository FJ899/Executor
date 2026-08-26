from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from executor.external_effect_receipt import (
    ExternalEffectReceiptError,
    _persist_verified_external_observation,
    _persist_verified_system_write_receipt,
    assess_system_write,
)


class BoundedGitHubEffectReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.evidence = Path(self.temp.name) / "evidence"

    def assert_effect_round_trip(
        self,
        *,
        action_kind: str,
        target: str,
        object_id: str,
        object_url: str,
        effect_bytes: bytes,
    ) -> None:
        receipt = _persist_verified_system_write_receipt(
            provider_response=b'{"ok":true}',
            effect_bytes=effect_bytes,
            evidence_directory=self.evidence,
            provider="GITHUB",
            action_kind=action_kind,
            target=target,
            provider_status=201,
            provider_message="Created",
            object_id=object_id,
            object_url=object_url,
        )
        result = assess_system_write(
            receipt=receipt,
            expected_provider="GITHUB",
            expected_action_kind=action_kind,
            expected_target=target,
            expected_effect_sha256=hashlib.sha256(effect_bytes).hexdigest(),
        )
        self.assertEqual(result["system_write"], "COMPLETED")
        self.assertEqual(result["verification"], "INDEPENDENT_READ_REQUIRED")

        observation = _persist_verified_external_observation(
            provider_response=b'{"observed":true}',
            observed_effect_bytes=effect_bytes,
            evidence_directory=self.evidence,
            provider="GITHUB",
            action_kind=action_kind,
            target=target,
            object_id=object_id,
            object_url=object_url,
            observed_at="2026-08-26T16:00:00Z",
        )
        self.assertEqual(observation.effect_sha256, receipt.effect_sha256)

    def test_create_issue_receipt(self) -> None:
        self.assert_effect_round_trip(
            action_kind="CREATE_ISSUE",
            target="FJ899/Executor",
            object_id="123",
            object_url="https://github.com/FJ899/Executor/issues/123",
            effect_bytes=b'{"title":"request","body":"canonical"}',
        )

    def test_create_git_ref_receipt(self) -> None:
        sha = "a" * 40
        self.assert_effect_round_trip(
            action_kind="CREATE_GIT_REF",
            target="FJ899/executor-pilot-target@refs/heads/executor-pilot/RUN-1",
            object_id=sha,
            object_url=f"https://github.com/FJ899/executor-pilot-target/commit/{sha}",
            effect_bytes=b'{"ref":"refs/heads/executor-pilot/RUN-1","sha":"aaaaaaaa"}',
        )

    def test_update_git_ref_receipt(self) -> None:
        sha = "b" * 40
        self.assert_effect_round_trip(
            action_kind="UPDATE_GIT_REF",
            target="FJ899/executor-pilot-target@refs/heads/executor-pilot/RUN-1",
            object_id=sha,
            object_url=f"https://github.com/FJ899/executor-pilot-target/commit/{sha}",
            effect_bytes=b'{"ref":"refs/heads/executor-pilot/RUN-1","sha":"bbbbbbbb"}',
        )

    def test_create_pull_request_receipt(self) -> None:
        self.assert_effect_round_trip(
            action_kind="CREATE_PULL_REQUEST",
            target="FJ899/executor-pilot-target",
            object_id="17",
            object_url="https://github.com/FJ899/executor-pilot-target/pull/17",
            effect_bytes=b'{"base":"main","head":"executor-pilot/RUN-1","draft":true}',
        )

    def test_ref_target_rejects_unsafe_ref_syntax(self) -> None:
        with self.assertRaisesRegex(ExternalEffectReceiptError, "safe branch ref"):
            _persist_verified_system_write_receipt(
                provider_response=b'{}',
                effect_bytes=b'x',
                evidence_directory=self.evidence,
                provider="GITHUB",
                action_kind="CREATE_GIT_REF",
                target="FJ899/executor-pilot-target@refs/heads/a..b",
                provider_status=500,
                provider_message="ambiguous",
            )


if __name__ == "__main__":
    unittest.main()
