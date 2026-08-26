from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.authority_result_recovery import (
    AuthorityResultRecoveryError,
    recover_local_result_binding,
)
from executor.github_effect_recovery import recover_interrupted_effect
from executor.github_effect_transaction import canonical_effect_bytes
from executor.github_trust import canonical_json


class _LocalBinder:
    def __init__(self) -> None:
        self.calls = 0

    def bind_result(self, *, execution_token, result):
        self.calls += 1
        digest = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
        return SimpleNamespace(
            result_sha256=digest,
            to_dict=lambda: {
                "execution_token": execution_token,
                "result_sha256": digest,
            },
        )


class _RecoveryLedger:
    def __init__(self) -> None:
        self.local = _LocalBinder()


class _ObserveOnlyGateway:
    def __init__(self) -> None:
        self.bound_payload = None
        self.write_calls = 0

    def bind_effect_payload(self, payload):
        self.bound_payload = payload

    def write(self, **kwargs):
        self.write_calls += 1
        raise AssertionError("restart recovery must never repeat provider write")

    def observe(self, **kwargs):
        raise AssertionError("observe is patched at transaction boundary in this wiring test")


class ProductRecoveryEntrypointTests(unittest.TestCase):
    def test_global_bound_local_unbound_recovery_binds_only_local_result(self) -> None:
        ledger = _RecoveryLedger()
        result = {
            "schema_version": "executor-github-effect-result/1.0",
            "status": "EFFECT_COMPLETED_AND_OBSERVED",
        }
        result_sha = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
        consumption = SimpleNamespace(
            authority_key="draft-pr:abc:CREATE_DRAFT_PR",
            payload_sha256="1" * 64,
            action_kind="CREATE_PULL_REQUEST",
            run_id="RUN-1",
            execution_token="token-1",
        )
        global_binding = {
            "authority_key": consumption.authority_key,
            "payload_sha256": consumption.payload_sha256,
            "action_kind": consumption.action_kind,
            "run_id": consumption.run_id,
            "result_sha256": result_sha,
        }

        recovered = recover_local_result_binding(
            ledger=ledger,
            consumption=consumption,
            result=result,
            global_binding=global_binding,
        )

        self.assertEqual(recovered.status, "GLOBAL_AND_LOCAL_RESULT_BOUND")
        self.assertEqual(recovered.result_sha256, result_sha)
        self.assertEqual(ledger.local.calls, 1)
        self.assertFalse(recovered.to_dict()["external_effect_retry_allowed"])

    def test_global_bound_local_recovery_rejects_different_result(self) -> None:
        ledger = _RecoveryLedger()
        consumption = SimpleNamespace(
            authority_key="draft-pr:abc:CREATE_DRAFT_PR",
            payload_sha256="2" * 64,
            action_kind="CREATE_PULL_REQUEST",
            run_id="RUN-2",
            execution_token="token-2",
        )
        with self.assertRaisesRegex(AuthorityResultRecoveryError, "differs from the already-bound global result"):
            recover_local_result_binding(
                ledger=ledger,
                consumption=consumption,
                result={"status": "DIFFERENT"},
                global_binding={
                    "authority_key": consumption.authority_key,
                    "payload_sha256": consumption.payload_sha256,
                    "action_kind": consumption.action_kind,
                    "run_id": consumption.run_id,
                    "result_sha256": "0" * 64,
                },
            )
        self.assertEqual(ledger.local.calls, 0)

    def test_restart_recovery_observes_without_repeating_external_write(self) -> None:
        payload = {
            "schema_version": "executor-draft-pr-effect/1.0",
            "title": "draft",
            "body": "bounded",
        }
        effect_bytes = canonical_effect_bytes(payload)
        gateway = _ObserveOnlyGateway()
        attempt = SimpleNamespace(attempt_id="ose-restart-1")
        consumption = SimpleNamespace()
        observed = {
            "schema_version": "executor-github-effect-result/1.0",
            "status": "RECOVERED_EXTERNAL_EFFECT",
        }

        with tempfile.TemporaryDirectory() as temp_name, \
             patch("executor.github_effect_recovery._load_attempts", return_value=[attempt]), \
             patch("executor.github_effect_recovery._recover_consumption", return_value=consumption), \
             patch(
                 "executor.github_effect_recovery.GitHubEffectTransaction.observe_and_bind",
                 return_value=observed,
             ):
            recovered = recover_interrupted_effect(
                ledger=SimpleNamespace(),
                gateway=gateway,
                run_id="RUN-RESTART",
                authority_key="draft-pr:abc:CREATE_DRAFT_PR",
                action_kind="CREATE_PULL_REQUEST",
                target="FJ899/executor-pilot-target",
                effect_payload=payload,
                effect_bytes=effect_bytes,
                evidence_directory=Path(temp_name),
                not_after="2099-01-01T00:00:00Z",
            )

        self.assertEqual(recovered["status"], "RECOVERED")
        self.assertFalse(recovered["automatic_retry_allowed"])
        self.assertFalse(recovered["external_write_repeated"])
        self.assertEqual(gateway.write_calls, 0)
        self.assertEqual(gateway.bound_payload, payload)


if __name__ == "__main__":
    unittest.main()
