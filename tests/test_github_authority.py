from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

from executor.authority_ledger import AtomicAuthorityLedger, AuthorityLedgerError
from executor.github_authority import (
    GlobalAuthorityExpiredError,
    GlobalAuthorityHttpError,
    GlobalAuthorityReplayError,
    GitHubGlobalAuthority,
    GovernedAuthorityLedger,
    ResultBindingRecoveryRequired,
)


class FakeGitHubTransport:
    def __init__(self, *, provider_time="2026-08-16T18:00:00Z"):
        self.provider_time = provider_time
        self.refs = {"refs/heads/main": "1" * 40}
        self.commits = {
            "1" * 40: {
                "sha": "1" * 40,
                "message": "base",
                "tree": {"sha": "2" * 40},
                "parents": [],
            }
        }
        self.counter = 1

    def _ref_from_url(self, url):
        marker = "/git/ref/"
        if marker in url:
            return "refs/" + unquote(url.split(marker, 1)[1])
        marker = "/git/refs/"
        if marker in url:
            return "refs/" + unquote(url.split(marker, 1)[1])
        raise AssertionError(url)

    def request_json(self, method, url, payload=None):
        if method == "GET" and "/git/ref/" in url:
            ref = self._ref_from_url(url)
            if ref not in self.refs:
                raise GlobalAuthorityHttpError(404, "not found")
            return {"ref": ref, "object": {"type": "commit", "sha": self.refs[ref]}}
        if method == "GET" and "/git/commits/" in url:
            sha = url.rsplit("/", 1)[-1]
            return dict(self.commits[sha])
        if method == "POST" and url.endswith("/git/commits"):
            self.counter += 1
            sha = f"{self.counter:040x}"
            self.commits[sha] = {
                "sha": sha,
                "message": payload["message"],
                "tree": {"sha": payload["tree"]},
                "parents": list(payload["parents"]),
                "committer": {"date": self.provider_time},
            }
            return {"sha": sha}
        if method == "POST" and url.endswith("/git/refs"):
            ref = payload["ref"]
            if ref in self.refs:
                raise GlobalAuthorityHttpError(422, "reference already exists")
            self.refs[ref] = payload["sha"]
            return {"ref": ref, "object": {"sha": payload["sha"]}}
        if method == "PATCH" and "/git/refs/" in url:
            ref = self._ref_from_url(url)
            if ref not in self.refs:
                raise GlobalAuthorityHttpError(404, "not found")
            candidate = self.commits[payload["sha"]]
            if payload.get("force") is not False or candidate["parents"] != [self.refs[ref]]:
                raise GlobalAuthorityHttpError(422, "not fast forward")
            self.refs[ref] = payload["sha"]
            return {"ref": ref, "object": {"sha": payload["sha"]}}
        raise AssertionError((method, url, payload))


class LoseCreateRefRaceTransport(FakeGitHubTransport):
    """Simulate another runner atomically creating the authority ref first."""

    def __init__(self):
        super().__init__()
        self.inject_race = True

    def request_json(self, method, url, payload=None):
        if method == "POST" and url.endswith("/git/refs") and self.inject_race:
            self.inject_race = False
            self.refs[payload["ref"]] = payload["sha"]
            raise GlobalAuthorityHttpError(422, "reference already exists")
        return super().request_json(method, url, payload)


class FailOnceBindLedger(AtomicAuthorityLedger):
    """Inject one local result-binding failure after the global component is bound."""

    def __init__(self, path):
        super().__init__(path)
        self.fail_next_bind = True

    def bind_result(self, *, execution_token, result):
        if self.fail_next_bind:
            self.fail_next_bind = False
            raise AuthorityLedgerError("injected local result-binding failure")
        return super().bind_result(execution_token=execution_token, result=result)


class GitHubGlobalAuthorityTests(unittest.TestCase):
    def test_same_key_is_global_across_instances_and_local_database_files(self):
        transport = FakeGitHubTransport()
        first_global = GitHubGlobalAuthority(
            repository="JTJ07/Executor",
            transport=transport,
        )
        second_global = GitHubGlobalAuthority(
            repository="JTJ07/Executor",
            transport=transport,
        )
        with tempfile.TemporaryDirectory() as directory:
            first = GovernedAuthorityLedger(
                AtomicAuthorityLedger(Path(directory) / "a.sqlite3"),
                first_global,
            )
            second = GovernedAuthorityLedger(
                AtomicAuthorityLedger(Path(directory) / "b.sqlite3"),
                second_global,
            )
            consumption = first.consume(
                authority_key="aap:stable-effect",
                payload_sha256="a" * 64,
                action_kind="EXTERNAL_PROJECT_EXECUTION",
                run_id="run-a",
            )
            with self.assertRaises(GlobalAuthorityReplayError):
                second.consume(
                    authority_key="aap:stable-effect",
                    payload_sha256="b" * 64,
                    action_kind="EXTERNAL_PROJECT_EXECUTION",
                    run_id="run-b",
                )
            final = first.bind_result(
                consumption=consumption,
                result={"status": "ACTION_COMPLETED_REVIEW_REQUIRED"},
            )
            self.assertEqual(final["state"], "FINAL")
            self.assertTrue(final["terminal_success"])
            self.assertEqual(final["binding_scope"], "GLOBAL_AND_LOCAL_COMPOSITE")
            self.assertEqual(final["global"]["state"], "FINAL")
            self.assertEqual(final["global"]["provider_state"], "GLOBAL_RESULT_BOUND")
            self.assertTrue(final["global"]["terminal_success"])
            self.assertFalse(final["global"]["requires_local_result_binding"])
            self.assertEqual(
                final["global"]["binding_scope"],
                "GLOBAL_COMPONENT_WITH_LOCAL_CONFIRMATION",
            )


    def test_global_bound_local_failure_is_recovery_required_not_terminal_success(self):
        transport = FakeGitHubTransport()
        authority = GitHubGlobalAuthority(
            repository="JTJ07/Executor",
            transport=transport,
        )
        with tempfile.TemporaryDirectory() as directory:
            local = FailOnceBindLedger(Path(directory) / "authority.sqlite3")
            ledger = GovernedAuthorityLedger(local, authority)
            key = "aap:partial-result-binding"
            result = {"status": "ACTION_COMPLETED_REVIEW_REQUIRED"}
            consumption = ledger.consume(
                authority_key=key,
                payload_sha256="f" * 64,
                action_kind="EXTERNAL_PROJECT_EXECUTION",
                run_id="partial-run",
            )

            with self.assertRaises(ResultBindingRecoveryRequired) as raised:
                ledger.bind_result(consumption=consumption, result=result)

            global_binding = raised.exception.global_binding
            self.assertEqual(global_binding["state"], "GLOBAL_RESULT_BOUND")
            self.assertFalse(global_binding["terminal_success"])
            self.assertTrue(global_binding["requires_local_result_binding"])
            self.assertEqual(local.get(key).state, "CONSUMED")

            ref_sha = transport.refs[global_binding["ref"]]
            receipt = authority._parse_receipt(transport.commits[ref_sha])
            self.assertEqual(receipt["state"], "GLOBAL_RESULT_BOUND")
            self.assertFalse(receipt["terminal_success"])
            self.assertTrue(receipt["requires_local_result_binding"])
            self.assertEqual(receipt["binding_scope"], "GLOBAL_COMPONENT_ONLY")

            recovered = ledger.bind_result(consumption=consumption, result=result)
            self.assertEqual(recovered["state"], "FINAL")
            self.assertTrue(recovered["terminal_success"])
            self.assertEqual(recovered["binding_scope"], "GLOBAL_AND_LOCAL_COMPOSITE")
            self.assertEqual(recovered["global"]["state"], "FINAL")
            self.assertEqual(
                recovered["global"]["provider_state"],
                "GLOBAL_RESULT_BOUND",
            )
            self.assertTrue(recovered["global"]["terminal_success"])
            self.assertFalse(recovered["global"]["requires_local_result_binding"])
            self.assertEqual(local.get(key).state, "FINAL")
            self.assertEqual(
                recovered["result_sha256"],
                recovered["global"]["result_sha256"],
            )

    def test_atomic_provider_ref_creation_loses_race_fail_closed(self):
        authority = GitHubGlobalAuthority(
            repository="JTJ07/Executor",
            transport=LoseCreateRefRaceTransport(),
        )
        with self.assertRaises(GlobalAuthorityReplayError):
            authority.reserve(
                authority_key="aap:race-effect",
                payload_sha256="c" * 64,
                action_kind="EXTERNAL_PROJECT_EXECUTION",
                run_id="race-run-a",
            )

    def test_provider_server_time_after_deadline_spends_authority_but_fails_closed(self):
        transport = FakeGitHubTransport(provider_time="2026-08-16T18:02:00Z")
        authority = GitHubGlobalAuthority(
            repository="JTJ07/Executor",
            transport=transport,
        )
        key = "aap:provider-expiry"
        with self.assertRaises(GlobalAuthorityExpiredError):
            authority.reserve(
                authority_key=key,
                payload_sha256="d" * 64,
                action_kind="EXTERNAL_PROJECT_EXECUTION",
                run_id="expiry-run",
                not_after="2026-08-16T18:01:00Z",
            )
        self.assertIn(GitHubGlobalAuthority._ref_for(key), transport.refs)

    def test_provider_server_time_before_deadline_is_bound_into_receipt_evidence(self):
        authority = GitHubGlobalAuthority(
            repository="JTJ07/Executor",
            transport=FakeGitHubTransport(provider_time="2026-08-16T18:00:00Z"),
        )
        reservation = authority.reserve(
            authority_key="aap:provider-fresh",
            payload_sha256="e" * 64,
            action_kind="EXTERNAL_PROJECT_EXECUTION",
            run_id="fresh-run",
            not_after="2026-08-16T18:01:00Z",
        )
        self.assertEqual(reservation.not_after, "2026-08-16T18:01:00Z")
        self.assertEqual(reservation.provider_created_at, "2026-08-16T18:00:00Z")

    def test_global_ref_name_depends_only_on_authority_key_not_run_id(self):
        key = "github-decision:IC_example"
        expected = "refs/heads/executor-authority/" + hashlib.sha256(
            key.encode("utf-8")
        ).hexdigest()
        self.assertEqual(GitHubGlobalAuthority._ref_for(key), expected)
        self.assertEqual(
            GitHubGlobalAuthority._ref_for(key),
            GitHubGlobalAuthority._ref_for(key),
        )


if __name__ == "__main__":
    unittest.main()
