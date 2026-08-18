from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from executor.authority_ledger import AtomicAuthorityLedger
from executor.github_authority import (
    GlobalAuthorityError,
    GlobalAuthorityReplayError,
    GovernedAuthorityLedger,
)
from executor.github_trust import GitHubTrustError, verify_github_decision, verify_github_request
from executor.frozen_pilot_authority import (
    FrozenPilotAuthorityError,
    authority_snapshot_sha256,
    validate_frozen_pilot_authority,
)
from executor.pilot_contract import (
    PilotContractError,
    apply_github_decision,
    build_pilot_draft,
    pilot_draft_sha256,
)
from tests.p4_test_support import FakeGlobalAuthority, governed_ledger
from tests.test_github_trust import (
    COMMENT_URL,
    ISSUE_URL,
    FakeSource,
    NOW,
    comment,
    commit_evidence,
    commit_url,
    decision_payload,
    issue,
    profile,
    request_payload,
)


class CountingSource(FakeSource):
    def __init__(self, values):
        super().__init__(values)
        self.calls: dict[str, int] = {}

    def fetch_json(self, url):
        self.calls[url] = self.calls.get(url, 0) + 1
        return super().fetch_json(url)


class FailFirstGlobalAuthority(FakeGlobalAuthority):
    def __init__(self, shared=None):
        super().__init__(shared)
        self.failures_remaining = 1
        self.attempted_payloads: list[str] = []

    def reserve(self, **kwargs):
        self.attempted_payloads.append(kwargs["payload_sha256"])
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise GlobalAuthorityError("synthetic CONTRACT_ACCEPT global failure")
        return super().reserve(**kwargs)


class RevocationCutoffTests(unittest.TestCase):
    def initial_pair(self, *, source_class=FakeSource):
        payload = request_payload()
        values = {
            ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
            commit_url(payload): commit_evidence(payload),
        }
        source = source_class(values)
        request = verify_github_request(
            source,
            profile=profile(),
            issue_number=61,
            now=NOW,
        )
        draft = build_pilot_draft(request)
        source.values[COMMENT_URL] = comment(
            decision_payload(request, pilot_draft_sha256(draft))
        )
        decision = verify_github_decision(
            source,
            profile=profile(),
            request=request,
            comment_id=9001,
            draft_sha256=pilot_draft_sha256(draft),
            now=NOW,
        )
        return source, draft, decision

    def freeze(self, source, draft, decision, ledger):
        with patch("executor.pilot_contract._utc_now", return_value=NOW):
            return apply_github_decision(
                draft=draft,
                decision=decision,
                source=source,
                profile=profile(),
                ledger=ledger,
            )

    def assert_no_local_authority(self, path):
        ledger = AtomicAuthorityLedger(path)
        self.assertIsNone(ledger.get("github-decision:IC_kwDO-decision"))
        self.assertEqual(ledger.unresolved(), ())

    def test_fc09_pre_cutoff_accept_edit_blocks_before_contract_accept(self):
        source, draft, decision = self.initial_pair()
        source.values[COMMENT_URL]["updated_at"] = "2026-08-16T00:01:01Z"
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "authority.sqlite3"
            shared = {}
            with self.assertRaisesRegex(GitHubTrustError, "edited"):
                self.freeze(
                    source,
                    draft,
                    decision,
                    governed_ledger(ledger_path, shared=shared),
                )
            self.assertEqual(shared, {})
            self.assert_no_local_authority(ledger_path)

    def test_fc10_pre_cutoff_accept_delete_blocks_before_contract_accept(self):
        source, draft, decision = self.initial_pair()
        del source.values[COMMENT_URL]
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "authority.sqlite3"
            shared = {}
            with self.assertRaisesRegex(GitHubTrustError, "unavailable"):
                self.freeze(
                    source,
                    draft,
                    decision,
                    governed_ledger(ledger_path, shared=shared),
                )
            self.assertEqual(shared, {})
            self.assert_no_local_authority(ledger_path)

    def test_fc11_pre_cutoff_request_mutation_invalidates_old_decision(self):
        source, draft, decision = self.initial_pair()
        changed = request_payload()
        changed["task"]["problem_statement"] = "materially changed before final verification"
        source.values[ISSUE_URL] = issue(json.dumps(changed, sort_keys=True))
        source.values[commit_url(changed)] = commit_evidence(changed)
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "authority.sqlite3"
            shared = {}
            with self.assertRaisesRegex(PilotContractError, "request changed"):
                self.freeze(
                    source,
                    draft,
                    decision,
                    governed_ledger(ledger_path, shared=shared),
                )
            self.assertEqual(shared, {})
            self.assert_no_local_authority(ledger_path)

    def test_fc12_failed_global_consumption_creates_no_authority_and_retry_reverifies(self):
        source, draft, decision = self.initial_pair(source_class=CountingSource)
        # Ignore the reads needed only to construct the initial review material.
        source.calls.clear()
        with tempfile.TemporaryDirectory() as directory:
            ledger_path = Path(directory) / "authority.sqlite3"
            global_authority = FailFirstGlobalAuthority({})
            ledger = GovernedAuthorityLedger(
                AtomicAuthorityLedger(ledger_path),
                global_authority,
            )
            with patch(
                "executor.pilot_contract._utc_now",
                side_effect=[NOW, NOW + timedelta(seconds=10)],
            ):
                with self.assertRaisesRegex(GlobalAuthorityError, "synthetic"):
                    apply_github_decision(
                        draft=draft,
                        decision=decision,
                        source=source,
                        profile=profile(),
                        ledger=ledger,
                    )
                self.assert_no_local_authority(ledger_path)
                self.assertEqual(global_authority.shared, {})
                frozen = apply_github_decision(
                    draft=draft,
                    decision=decision,
                    source=source,
                    profile=profile(),
                    ledger=ledger,
                )
            self.assertEqual(source.calls[ISSUE_URL], 2)
            self.assertEqual(source.calls[COMMENT_URL], 2)
            self.assertEqual(len(global_authority.attempted_payloads), 2)
            self.assertNotEqual(
                global_authority.attempted_payloads[0],
                global_authority.attempted_payloads[1],
            )
            self.assertEqual(frozen["status"], "AUTHORIZED_AND_FROZEN")
            self.assertEqual(frozen["decision_consumption"]["global"]["state"], "FINAL")

    def test_fc13_post_cutoff_accept_edit_does_not_revoke_frozen_authority(self):
        source, draft, decision = self.initial_pair()
        with tempfile.TemporaryDirectory() as directory:
            frozen = self.freeze(
                source,
                draft,
                decision,
                governed_ledger(Path(directory) / "authority.sqlite3", shared={}),
            )
            source.values[COMMENT_URL]["body"] = "post-cutoff mutation"
            source.values[COMMENT_URL]["updated_at"] = "2026-08-16T00:05:00Z"
            request_authority, decision_authority = validate_frozen_pilot_authority(frozen)
            self.assertEqual(
                request_authority.evidence_ref,
                frozen["contract"]["request_evidence"]["evidence_ref"],
            )
            self.assertEqual(
                decision_authority.evidence_ref,
                frozen["contract"]["decision_evidence"]["evidence_ref"],
            )

    def test_fc14_post_cutoff_accept_delete_does_not_revoke_frozen_authority(self):
        source, draft, decision = self.initial_pair()
        with tempfile.TemporaryDirectory() as directory:
            frozen = self.freeze(
                source,
                draft,
                decision,
                governed_ledger(Path(directory) / "authority.sqlite3", shared={}),
            )
            del source.values[COMMENT_URL]
            _, decision_authority = validate_frozen_pilot_authority(frozen)
            self.assertEqual(decision_authority.decision, "ACCEPT")

    def test_fc15_post_cutoff_request_edit_does_not_change_frozen_contract(self):
        source, draft, decision = self.initial_pair()
        with tempfile.TemporaryDirectory() as directory:
            frozen = self.freeze(
                source,
                draft,
                decision,
                governed_ledger(Path(directory) / "authority.sqlite3", shared={}),
            )
            original_hash = frozen["contract"]["request_evidence"]["body_sha256"]
            changed = request_payload()
            changed["task"]["problem_statement"] = "post-cutoff provider mutation"
            source.values[ISSUE_URL] = issue(json.dumps(changed, sort_keys=True))
            request_authority, _ = validate_frozen_pilot_authority(frozen)
            self.assertEqual(request_authority.body_sha256, original_hash)

    def test_fc16_snapshot_substitution_blocks(self):
        source, draft, decision = self.initial_pair()
        with tempfile.TemporaryDirectory() as directory:
            frozen = self.freeze(
                source,
                draft,
                decision,
                governed_ledger(Path(directory) / "authority.sqlite3", shared={}),
            )

            with self.subTest("different provider identity"):
                altered_identity = copy.deepcopy(frozen)
                altered_identity["contract"]["authority_snapshot"]["decision"][
                    "provider_event"
                ]["node_id"] = "IC_substituted"
                with self.assertRaises(FrozenPilotAuthorityError):
                    validate_frozen_pilot_authority(altered_identity)

            with self.subTest("rehash cannot escape consumed receipt"):
                altered = copy.deepcopy(frozen)
                snapshot = altered["contract"]["authority_snapshot"]
                snapshot["verified_at"] = "2026-08-16T00:02:10Z"
                new_hash = authority_snapshot_sha256(snapshot)
                altered["contract"]["authority_snapshot_sha256"] = new_hash
                altered["authority_snapshot_sha256"] = new_hash
                with self.assertRaisesRegex(FrozenPilotAuthorityError, "snapshot binding mismatch"):
                    validate_frozen_pilot_authority(altered)

    def test_fc17_contract_accept_replay_blocks_across_run_id_and_fresh_sqlite(self):
        source, draft, decision = self.initial_pair()
        with tempfile.TemporaryDirectory() as directory:
            shared = {}
            first_path = Path(directory) / "first.sqlite3"
            frozen = self.freeze(
                source,
                draft,
                decision,
                governed_ledger(first_path, shared=shared),
            )
            receipt = frozen["decision_consumption"]
            second = governed_ledger(Path(directory) / "fresh.sqlite3", shared=shared)
            with self.assertRaises(GlobalAuthorityReplayError):
                second.consume(
                    authority_key=receipt["authority_key"],
                    payload_sha256=receipt["payload_sha256"],
                    action_kind=receipt["action_kind"],
                    run_id="different-run-id",
                    not_after=receipt["global"]["not_after"],
                )


    def test_run_pilot_uses_frozen_authority_not_mutable_provider_currentness(self):
        import inspect
        from executor import cli

        source = inspect.getsource(cli.main)
        block = source.split('if args.command == "run-pilot":', 1)[1].split(
            'if args.command == "materialize-pilot-proposal":', 1
        )[0]
        self.assertIn("validate_frozen_pilot_authority", block)
        self.assertNotIn("verify_github_request(", block)
        self.assertNotIn("verify_github_decision(", block)

    def test_snapshot_proves_direct_human_signal_was_present_at_cutoff(self):
        source, draft, decision = self.initial_pair()
        with tempfile.TemporaryDirectory() as directory:
            frozen = self.freeze(
                source,
                draft,
                decision,
                governed_ledger(Path(directory) / "authority.sqlite3", shared={}),
            )
            snapshot = frozen["contract"]["authority_snapshot"]
            self.assertTrue(
                snapshot["request"]["provider_event"]["performed_via_github_app_present"]
            )
            self.assertTrue(
                snapshot["decision"]["provider_event"]["performed_via_github_app_present"]
            )
            validate_frozen_pilot_authority(frozen)


if __name__ == "__main__":
    unittest.main()
