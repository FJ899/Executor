from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from executor.github_authority import GlobalAuthorityReplayError
from executor.github_trust import (
    GitHubTrustError,
    GitHubTrustProfile,
    VerifiedGitHubRequest,
    verify_github_decision,
    verify_github_request,
)
from executor.pilot_contract import (
    apply_github_decision,
    build_pilot_draft,
    pilot_draft_sha256,
)
from tests.p4_test_support import governed_ledger


NOW = datetime(2026, 8, 16, 0, 2, tzinfo=timezone.utc)
REPOSITORY = "FJ899/Executor"
ISSUE_URL = f"https://api.github.com/repos/{REPOSITORY}/issues/61"
COMMENT_URL = f"https://api.github.com/repos/{REPOSITORY}/issues/comments/9001"


def commit_url(payload):
    target = payload["target"]
    return (
        f"https://api.github.com/repos/{target['repository']}/git/commits/"
        f"{target['commit']}"
    )


def commit_evidence(payload):
    target = payload["target"]
    return {"sha": target["commit"], "tree": {"sha": target["tree"]}}


class FakeSource:
    def __init__(self, values):
        self.values = values

    def fetch_json(self, url):
        if url not in self.values:
            raise GitHubTrustError(f"GitHub provider event is unavailable: {url}")
        return copy.deepcopy(self.values[url])


def profile() -> GitHubTrustProfile:
    return GitHubTrustProfile.from_dict(
        {
            "schema_version": "executor-github-trust-profile/1.0",
            "profile_id": "test-profile",
            "intake_repository": REPOSITORY,
            "allowed_actor": {"login": "FJ899", "id": 275481581},
            "allowed_target_repositories": ["FJ899/scriptops"],
            "max_decision_lifetime_seconds": 3600,
        }
    )


def request_payload():
    return {
        "schema_version": "executor-github-request/1.0",
        "request_id": "pilot-scriptops-001",
        "target": {
            "repository": "FJ899/scriptops",
            "commit": "a" * 40,
            "tree": "b" * 40,
        },
        "task": {
            "class": "BOUNDED_CORRECTNESS_OR_QUALITY_FIX",
            "problem_statement": "Select the latest candidate by numeric version.",
            "allowed_paths": ["phase6/scriptops-v2-hardening.py"],
            "protected_paths": ["tests/**", ".github/**"],
            "precondition_argv": [["python", "-c", "raise SystemExit(1)"]],
            "postcondition_argv": [["python", "-c", "raise SystemExit(0)"]],
            "regression_argv": [["python", "-m", "unittest", "discover", "-s", "tests"]],
            "max_production_files": 1,
            "max_patch_lines": 120,
        },
        "expires_at": "2026-08-16T01:00:00Z",
        "nonce": "request-nonce-001",
    }


def issue(body=None):
    return {
        "url": ISSUE_URL,
        "repository_url": f"https://api.github.com/repos/{REPOSITORY}",
        "number": 61,
        "id": 7001,
        "node_id": "I_kwDO-request",
        "html_url": "https://github.com/FJ899/Executor/issues/61",
        "state": "open",
        "body": body or json.dumps(request_payload(), sort_keys=True),
        "created_at": "2026-08-16T00:00:00Z",
        "updated_at": "2026-08-16T00:00:00Z",
        "author_association": "OWNER",
        "performed_via_github_app": None,
        "user": {"login": "FJ899", "id": 275481581, "type": "User"},
    }


def decision_payload(request, draft_sha, decision="ACCEPT"):
    return {
        "schema_version": "executor-github-decision/1.0",
        "request": {
            "repository": request.repository,
            "issue_number": request.issue_number,
            "issue_node_id": request.issue_node_id,
            "body_sha256": request.body_sha256,
        },
        "draft_sha256": draft_sha,
        "decision": decision,
        "valid_for_seconds": 1800,
        "nonce": "decision-nonce-001",
    }


def comment(payload):
    return {
        "url": COMMENT_URL,
        "issue_url": ISSUE_URL,
        "id": 9001,
        "node_id": "IC_kwDO-decision",
        "body": json.dumps(payload, sort_keys=True),
        "created_at": "2026-08-16T00:01:00Z",
        "updated_at": "2026-08-16T00:01:00Z",
        "author_association": "OWNER",
        "performed_via_github_app": None,
        "user": {"login": "FJ899", "id": 275481581, "type": "User"},
    }


class GitHubTrustTests(unittest.TestCase):
    def verified_pair(self, *, decision="ACCEPT"):
        payload = request_payload()
        values = {
            ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
            commit_url(payload): commit_evidence(payload),
        }
        source = FakeSource(values)
        request = verify_github_request(
            source,
            profile=profile(),
            issue_number=61,
            now=NOW,
        )
        draft = build_pilot_draft(request)
        draft_sha = pilot_draft_sha256(draft)
        values[COMMENT_URL] = comment(decision_payload(request, draft_sha, decision))
        verified = verify_github_decision(
            source,
            profile=profile(),
            request=request,
            comment_id=9001,
            draft_sha256=draft_sha,
            now=NOW,
        )
        return source, request, draft, verified

    def apply_final(self, *, source, draft, decision, ledger):
        with patch("executor.pilot_contract._utc_now", return_value=NOW):
            return apply_github_decision(
                draft=draft,
                decision=decision,
                source=source,
                profile=profile(),
                ledger=ledger,
            )

    def test_exact_github_accept_freezes_once_globally(self):
        source, _, draft, decision = self.verified_pair()
        with tempfile.TemporaryDirectory() as directory:
            shared = {}
            result = self.apply_final(
                source=source,
                draft=draft,
                decision=decision,
                ledger=governed_ledger(Path(directory) / "ledger-a.sqlite3", shared=shared),
            )
            self.assertEqual(result["status"], "AUTHORIZED_AND_FROZEN")
            self.assertTrue(result["executable"])
            self.assertEqual(result["contract"]["status"], "AUTHORIZED_AND_FROZEN")
            self.assertEqual(result["decision_consumption"]["global"]["state"], "FINAL")
            with self.assertRaises(GlobalAuthorityReplayError):
                self.apply_final(
                    source=source,
                    draft=draft,
                    decision=decision,
                    ledger=governed_ledger(
                        Path(directory) / "different-ledger.sqlite3",
                        shared=shared,
                    ),
                )

    def test_accept_uses_provider_created_at_without_payload_prediction(self):
        payload = request_payload()
        values = {
            ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
            commit_url(payload): commit_evidence(payload),
        }
        source = FakeSource(values)
        request = verify_github_request(
            source,
            profile=profile(),
            issue_number=61,
            now=NOW,
        )
        draft = build_pilot_draft(request)
        decision = decision_payload(request, pilot_draft_sha256(draft))
        self.assertNotIn("issued_at", decision)
        self.assertNotIn("expires_at", decision)
        provider_comment = comment(decision)
        provider_comment["created_at"] = "2026-08-16T00:01:37Z"
        provider_comment["updated_at"] = provider_comment["created_at"]
        source.values[COMMENT_URL] = provider_comment
        verified = verify_github_decision(
            source,
            profile=profile(),
            request=request,
            comment_id=9001,
            draft_sha256=pilot_draft_sha256(draft),
            now=NOW,
        )
        self.assertEqual(verified.created_at, "2026-08-16T00:01:37Z")
        self.assertEqual(verified.expires_at, "2026-08-16T00:31:37Z")

    def test_modify_and_reject_never_freeze(self):
        for choice, status in (("MODIFY", "MODIFICATION_REQUIRED"), ("REJECT", "REJECTED")):
            with self.subTest(choice=choice), tempfile.TemporaryDirectory() as directory:
                source, _, draft, decision = self.verified_pair(decision=choice)
                result = self.apply_final(
                    source=source,
                    draft=draft,
                    decision=decision,
                    ledger=governed_ledger(Path(directory) / "ledger.sqlite3"),
                )
                self.assertEqual(result["status"], status)
                self.assertFalse(result["executable"])
                self.assertNotIn("contract", result)

    def test_wrong_actor_blocks(self):
        source, request, draft, _ = self.verified_pair()
        bad = comment(decision_payload(request, pilot_draft_sha256(draft)))
        bad["user"] = {"login": "mallory", "id": 5, "type": "User"}
        source.values[COMMENT_URL] = bad
        with self.assertRaisesRegex(GitHubTrustError, "allowed GitHub user"):
            verify_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256=pilot_draft_sha256(draft),
                now=NOW,
            )

    def test_app_mediated_request_blocks(self):
        payload = request_payload()
        mediated = issue(json.dumps(payload, sort_keys=True))
        mediated["performed_via_github_app"] = {"id": 123, "slug": "executor-bot"}
        source = FakeSource(
            {
                ISSUE_URL: mediated,
                commit_url(payload): commit_evidence(payload),
            }
        )
        with self.assertRaisesRegex(GitHubTrustError, "app-mediated"):
            verify_github_request(source, profile=profile(), issue_number=61, now=NOW)

    def test_missing_request_direct_human_signal_blocks(self):
        payload = request_payload()
        missing = issue(json.dumps(payload, sort_keys=True))
        missing.pop("performed_via_github_app")
        source = FakeSource(
            {
                ISSUE_URL: missing,
                commit_url(payload): commit_evidence(payload),
            }
        )
        with self.assertRaisesRegex(GitHubTrustError, "provider-verifiable"):
            verify_github_request(source, profile=profile(), issue_number=61, now=NOW)

    def test_app_mediated_decision_blocks(self):
        source, request, draft, _ = self.verified_pair()
        mediated = comment(decision_payload(request, pilot_draft_sha256(draft)))
        mediated["performed_via_github_app"] = {"id": 123, "slug": "executor-bot"}
        source.values[COMMENT_URL] = mediated
        with self.assertRaisesRegex(GitHubTrustError, "app-mediated"):
            verify_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256=pilot_draft_sha256(draft),
                now=NOW,
            )

    def test_missing_decision_direct_human_signal_blocks(self):
        source, request, draft, _ = self.verified_pair()
        missing = comment(decision_payload(request, pilot_draft_sha256(draft)))
        missing.pop("performed_via_github_app")
        source.values[COMMENT_URL] = missing
        with self.assertRaisesRegex(GitHubTrustError, "provider-verifiable"):
            verify_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256=pilot_draft_sha256(draft),
                now=NOW,
            )

    def test_request_commit_tree_must_match_live_github(self):
        payload = request_payload()
        source = FakeSource(
            {
                ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
                commit_url(payload): {
                    "sha": payload["target"]["commit"],
                    "tree": {"sha": "f" * 40},
                },
            }
        )
        with self.assertRaisesRegex(GitHubTrustError, "commit/tree"):
            verify_github_request(source, profile=profile(), issue_number=61, now=NOW)

    def test_observation_time_does_not_change_draft_identity(self):
        payload = request_payload()
        source = FakeSource(
            {
                ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
                commit_url(payload): commit_evidence(payload),
            }
        )
        first = verify_github_request(source, profile=profile(), issue_number=61, now=NOW)
        second = verify_github_request(
            source,
            profile=profile(),
            issue_number=61,
            now=NOW + timedelta(minutes=10),
        )
        self.assertNotEqual(first.observed_at, second.observed_at)
        self.assertEqual(
            pilot_draft_sha256(build_pilot_draft(first)),
            pilot_draft_sha256(build_pilot_draft(second)),
        )

    def test_wrong_issue_or_request_hash_blocks(self):
        for field, value in (("issue_number", 62), ("body_sha256", "f" * 64)):
            with self.subTest(field=field):
                source, request, draft, _ = self.verified_pair()
                invalid = decision_payload(request, pilot_draft_sha256(draft))
                invalid["request"][field] = value
                source.values[COMMENT_URL] = comment(invalid)
                with self.assertRaisesRegex(GitHubTrustError, "stale or mismatched"):
                    verify_github_decision(
                        source,
                        profile=profile(),
                        request=request,
                        comment_id=9001,
                        draft_sha256=pilot_draft_sha256(draft),
                        now=NOW,
                    )

    def test_changed_request_content_invalidates_decision_binding(self):
        source, request, draft, _ = self.verified_pair()
        changed = request_payload()
        changed["task"]["problem_statement"] = "changed after approval"
        source.values[ISSUE_URL] = issue(json.dumps(changed, sort_keys=True))
        source.values[commit_url(changed)] = commit_evidence(changed)
        current = verify_github_request(source, profile=profile(), issue_number=61, now=NOW)
        self.assertNotEqual(
            pilot_draft_sha256(draft),
            pilot_draft_sha256(build_pilot_draft(current)),
        )
        with self.assertRaisesRegex(GitHubTrustError, "different draft|stale or mismatched"):
            verify_github_decision(
                source,
                profile=profile(),
                request=current,
                comment_id=9001,
                draft_sha256=pilot_draft_sha256(build_pilot_draft(current)),
                now=NOW,
            )

    def test_draft_mismatch_blocks(self):
        source, request, _, _ = self.verified_pair()
        with self.assertRaisesRegex(GitHubTrustError, "different draft"):
            verify_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256="f" * 64,
                now=NOW,
            )

    def test_decision_lifetime_cannot_exceed_profile(self):
        source, request, draft, _ = self.verified_pair()
        invalid = decision_payload(request, pilot_draft_sha256(draft))
        invalid["valid_for_seconds"] = 3601
        source.values[COMMENT_URL] = comment(invalid)
        with self.assertRaisesRegex(GitHubTrustError, "valid_for_seconds"):
            verify_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256=pilot_draft_sha256(draft),
                now=NOW,
            )

    def test_edited_or_expired_decision_blocks(self):
        source, request, draft, _ = self.verified_pair()
        edited = source.values[COMMENT_URL]
        edited["updated_at"] = "2026-08-16T00:01:01Z"
        with self.assertRaisesRegex(GitHubTrustError, "edited"):
            verify_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256=pilot_draft_sha256(draft),
                now=NOW,
            )
        edited["updated_at"] = edited["created_at"]
        with self.assertRaisesRegex(GitHubTrustError, "fresh"):
            verify_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256=pilot_draft_sha256(draft),
                now=datetime(2026, 8, 16, 0, 31, tzinfo=timezone.utc),
            )

    def test_verified_evidence_cannot_be_constructed_by_caller(self):
        with self.assertRaisesRegex(GitHubTrustError, "verify_github_request"):
            VerifiedGitHubRequest(
                profile_id="x",
                repository=REPOSITORY,
                issue_number=1,
                issue_id=1,
                issue_node_id="x",
                actor_login="FJ899",
                actor_id=275481581,
                body_sha256="a" * 64,
                created_at="2026-08-16T00:00:00Z",
                observed_at="2026-08-16T00:00:00Z",
                payload={},
            )


if __name__ == "__main__":
    unittest.main()
