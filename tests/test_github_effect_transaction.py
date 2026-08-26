from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from executor.github_effect_transaction import (
    GitHubEffectTransaction,
    ProviderReadResult,
    ProviderWriteResult,
    canonical_effect_bytes,
)


class FakeLedger:
    def __init__(self) -> None:
        self.consumes = []
        self.bindings = []

    def consume(self, **kwargs):
        self.consumes.append(kwargs)
        return {"execution_token": "fake", **kwargs}

    def bind_result(self, *, consumption, result):
        self.bindings.append((consumption, result))
        return {
            "state": "FINAL",
            "authority_key": consumption["authority_key"],
            "payload_sha256": consumption["payload_sha256"],
            "action_kind": consumption["action_kind"],
            "run_id": consumption["run_id"],
        }


class FakeGateway:
    def __init__(self, *, payload: dict, write_mode: str, observe_mode: str) -> None:
        self.payload = payload
        self.write_mode = write_mode
        self.observe_mode = observe_mode
        self.write_calls = 0
        self.observe_calls = 0

    def write(self, *, action_kind, target, effect_bytes, correlation_id):
        self.write_calls += 1
        if self.write_mode == "raise":
            raise TimeoutError("provider timeout after send")
        if self.write_mode == "5xx":
            return ProviderWriteResult(
                provider_status=503,
                provider_message="Service unavailable",
                raw_response=b'{"message":"unavailable"}',
            )
        return ProviderWriteResult(
            provider_status=201,
            provider_message="Created",
            raw_response=b'{"number":9}',
            object_id="9",
            object_url="https://github.com/FJ899/Executor/issues/9",
        )

    def observe(self, *, action_kind, target, effect_sha256, correlation_id):
        self.observe_calls += 1
        if self.observe_mode == "incomplete":
            return ProviderReadResult(
                complete=False,
                exists=False,
                raw_response=b'{"message":"timeout"}',
            )
        if self.observe_mode == "absent":
            return ProviderReadResult(
                complete=True,
                exists=False,
                raw_response=b"[]",
            )
        return ProviderReadResult(
            complete=True,
            exists=True,
            raw_response=b'[{"number":9}]',
            observed_effect_bytes=canonical_effect_bytes(self.payload),
            object_id="9",
            object_url="https://github.com/FJ899/Executor/issues/9",
        )


class GitHubEffectTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.evidence = Path(self.temp.name) / "evidence"
        self.payload = {
            "schema_version": "test-effect/1.0",
            "title": "canonical request",
            "body": "{}",
        }
        self.effect = canonical_effect_bytes(self.payload)

    def transaction(self, ledger) -> GitHubEffectTransaction:
        return GitHubEffectTransaction(
            run_id="FORM-request-1",
            authority_key="formation:abc:CREATE_AUTHORITY_ISSUE",
            action_kind="CREATE_ISSUE",
            target="FJ899/Executor",
            effect_bytes=self.effect,
            not_after="2099-01-01T00:00:00Z",
            evidence_directory=self.evidence,
            ledger=ledger,
        )

    def test_success_requires_write_receipt_then_fresh_observation(self) -> None:
        ledger = FakeLedger()
        gateway = FakeGateway(payload=self.payload, write_mode="success", observe_mode="present")
        result = self.transaction(ledger).execute(gateway)
        self.assertEqual(result["status"], "EFFECT_COMPLETED_AND_OBSERVED")
        self.assertEqual(gateway.write_calls, 1)
        self.assertEqual(gateway.observe_calls, 1)
        self.assertEqual(len(ledger.bindings), 1)

    def test_timeout_after_send_never_retries_and_observation_recovers_effect(self) -> None:
        ledger = FakeLedger()
        gateway = FakeGateway(payload=self.payload, write_mode="raise", observe_mode="present")
        result = self.transaction(ledger).execute(gateway)
        self.assertEqual(result["status"], "RECOVERED_EXTERNAL_EFFECT")
        self.assertEqual(gateway.write_calls, 1)
        self.assertEqual(gateway.observe_calls, 1)
        self.assertFalse(result["automatic_retry_allowed"])

    def test_5xx_is_ambiguous_until_read_back_finds_exact_effect(self) -> None:
        ledger = FakeLedger()
        gateway = FakeGateway(payload=self.payload, write_mode="5xx", observe_mode="present")
        result = self.transaction(ledger).execute(gateway)
        self.assertEqual(result["status"], "RECOVERED_EXTERNAL_EFFECT")
        self.assertEqual(gateway.write_calls, 1)
        self.assertEqual(gateway.observe_calls, 1)

    def test_complete_absence_never_retries_under_same_authority(self) -> None:
        ledger = FakeLedger()
        gateway = FakeGateway(payload=self.payload, write_mode="raise", observe_mode="absent")
        result = self.transaction(ledger).execute(gateway)
        self.assertEqual(result["status"], "NO_EFFECT_CONFIRMED")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertTrue(result["next_attempt_requires_new_authority"])
        self.assertEqual(gateway.write_calls, 1)

    def test_incomplete_observation_is_recovery_required(self) -> None:
        ledger = FakeLedger()
        gateway = FakeGateway(payload=self.payload, write_mode="raise", observe_mode="incomplete")
        result = self.transaction(ledger).execute(gateway)
        self.assertEqual(result["status"], "RECOVERY_REQUIRED")
        self.assertFalse(result["automatic_retry_allowed"])
        self.assertEqual(len(ledger.bindings), 0)


if __name__ == "__main__":
    unittest.main()
