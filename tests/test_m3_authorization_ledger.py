import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from executor.action_authorization import AuthorizationDecision
from executor.m3.authorization_ledger import (
    ActionResult,
    AuthorizationConsumptionLedger,
    AuthorizationLedgerIntegrityError,
    AuthorizationReplayError,
)


ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64


class AuthorizationConsumptionLedgerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "ledger"
        self.root.mkdir(mode=0o700)
        self.key = b"ledger-key" * 4
        self.ledger = AuthorizationConsumptionLedger(
            self.root, authentication_key=self.key, key_id="ledger-key-1"
        )

    def tearDown(self):
        self.temp.cleanup()

    def decision(self, packet_id="PACKET-1"):
        return AuthorizationDecision(
            packet_id=packet_id,
            payload_sha256=ONE,
            action_kind="WRITE_REPOSITORY",
            expires_at="2030-01-01T00:00:00Z",
            issuer_role="USER",
            issuer_id="user-1",
            issuer_evidence_ref="evidence-1",
        )

    def action(self):
        return {"kind": "WRITE_REPOSITORY", "argv": [], "paths": ["README.md"]}

    def result(self, status="SUCCEEDED"):
        return ActionResult(
            status=status,
            exit_code=0 if status == "SUCCEEDED" else 1,
            stdout_sha256=ZERO,
            stderr_sha256=ONE,
            output_sha256=TWO,
            completed_at="2026-08-02T16:00:00Z",
        )

    def test_consume_before_action_and_bind_exactly_one_result(self):
        receipt = self.ledger.consume(
            self.decision(), run_id="RUN-1", action_binding=self.action()
        )
        public = receipt.public_dict()
        self.assertNotIn("result_binding_token", public)
        bound = self.ledger.bind_result(
            packet_id="PACKET-1",
            result_binding_token=receipt.result_binding_token,
            result=self.result(),
        )
        self.assertEqual(bound.previous_event_hash, receipt.event_hash)
        self.ledger.verify_integrity()
        with self.assertRaisesRegex(AuthorizationLedgerIntegrityError, "already bound"):
            self.ledger.bind_result(
                packet_id="PACKET-1",
                result_binding_token=receipt.result_binding_token,
                result=self.result("FAILED"),
            )

    def test_parallel_reuse_has_exactly_one_winner(self):
        def attempt(_):
            ledger = AuthorizationConsumptionLedger(
                self.root, authentication_key=self.key, key_id="ledger-key-1"
            )
            try:
                ledger.consume(
                    self.decision(), run_id="RUN-1", action_binding=self.action()
                )
                return "won"
            except AuthorizationReplayError:
                return "replay"

        with ThreadPoolExecutor(max_workers=16) as pool:
            outcomes = list(pool.map(attempt, range(32)))
        self.assertEqual(outcomes.count("won"), 1)
        self.assertEqual(outcomes.count("replay"), 31)
        self.ledger.verify_integrity()

    def test_consumed_packet_remains_consumed_without_or_after_failed_result(self):
        receipt = self.ledger.consume(
            self.decision(), run_id="RUN-1", action_binding=self.action()
        )
        with self.assertRaises(AuthorizationReplayError):
            self.ledger.consume(
                self.decision(), run_id="RUN-1", action_binding=self.action()
            )
        self.ledger.bind_result(
            packet_id="PACKET-1",
            result_binding_token=receipt.result_binding_token,
            result=self.result("FAILED"),
        )
        with self.assertRaises(AuthorizationReplayError):
            self.ledger.consume(
                self.decision(), run_id="RUN-1", action_binding=self.action()
            )

    def test_wrong_token_action_kind_and_ineligible_decision_fail_closed(self):
        receipt = self.ledger.consume(
            self.decision(), run_id="RUN-1", action_binding=self.action()
        )
        with self.assertRaisesRegex(AuthorizationLedgerIntegrityError, "token"):
            self.ledger.bind_result(
                packet_id="PACKET-1",
                result_binding_token="wrong",
                result=self.result(),
            )
        with self.assertRaisesRegex(AuthorizationLedgerIntegrityError, "Action kind"):
            self.ledger.consume(
                self.decision("PACKET-2"),
                run_id="RUN-1",
                action_binding={"kind": "MERGE_PULL_REQUEST"},
            )
        with self.assertRaisesRegex(AuthorizationLedgerIntegrityError, "not eligible"):
            self.ledger.consume(
                replace(self.decision("PACKET-3"), ready_for_atomic_consumption=False),
                run_id="RUN-1",
                action_binding=self.action(),
            )
        self.assertTrue(receipt.result_binding_token)

    def test_database_tamper_is_detected_even_if_plain_hash_field_is_changed(self):
        self.ledger.consume(
            self.decision(), run_id="RUN-1", action_binding=self.action()
        )
        with sqlite3.connect(self.ledger.database) as connection:
            connection.execute(
                "UPDATE consumptions SET action_binding_sha256 = ? WHERE packet_id = ?",
                (TWO, "PACKET-1"),
            )
        with self.assertRaisesRegex(AuthorizationLedgerIntegrityError, "integrity"):
            self.ledger.verify_integrity()


if __name__ == "__main__":
    unittest.main()
