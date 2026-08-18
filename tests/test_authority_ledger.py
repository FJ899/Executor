from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from executor.authority_ledger import (
    AtomicAuthorityLedger,
    AuthorityLedgerError,
    AuthorityReplayError,
)


class AuthorityLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "authority.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_competing_consumers_get_exactly_one_authority(self):
        def attempt(index):
            try:
                return AtomicAuthorityLedger(self.path).consume(
                    authority_key="aap:packet-001",
                    payload_sha256="a" * 64,
                    action_kind="EXTERNAL_PROJECT_EXECUTION",
                    run_id=f"run-{index}",
                )
            except AuthorityReplayError:
                return None

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        winners = [result for result in results if result is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(AtomicAuthorityLedger(self.path).unresolved()), 1)

    def test_result_binding_is_exact_and_idempotent(self):
        ledger = AtomicAuthorityLedger(self.path)
        consumption = ledger.consume(
            authority_key="aap:packet-002",
            payload_sha256="b" * 64,
            action_kind="WRITE_REPOSITORY",
            run_id="run-002",
        )
        first = ledger.bind_result(
            execution_token=consumption.execution_token,
            result={"status": "FAILED", "reason": "postcondition"},
        )
        second = AtomicAuthorityLedger(self.path).bind_result(
            execution_token=consumption.execution_token,
            result={"reason": "postcondition", "status": "FAILED"},
        )
        self.assertEqual(first.result_sha256, second.result_sha256)
        self.assertEqual(first.state, "FINAL")
        self.assertEqual(AtomicAuthorityLedger(self.path).unresolved(), ())
        with self.assertRaisesRegex(AuthorityLedgerError, "different content"):
            ledger.bind_result(
                execution_token=consumption.execution_token,
                result={"status": "PASS"},
            )

    def test_restart_preserves_replay_and_unresolved_crash_state(self):
        first = AtomicAuthorityLedger(self.path)
        first.consume(
            authority_key="github-decision:node-1",
            payload_sha256="c" * 64,
            action_kind="CONTRACT_ACCEPT",
            run_id="request-1",
        )
        restarted = AtomicAuthorityLedger(self.path)
        self.assertEqual(len(restarted.unresolved()), 1)
        with self.assertRaises(AuthorityReplayError):
            restarted.consume(
                authority_key="github-decision:node-1",
                payload_sha256="c" * 64,
                action_kind="CONTRACT_ACCEPT",
                run_id="request-1",
            )


if __name__ == "__main__":
    unittest.main()
