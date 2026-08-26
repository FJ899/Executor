from __future__ import annotations

import base64
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from executor.github_effect_transaction import canonical_effect_bytes
from executor.github_trust import GitHubTrustProfile, canonical_json
from executor.product_draft_pr_gateway import ProductGitHubDraftPrGateway
from executor.product_draft_pr_retry import (
    DraftPrRetryError,
    ProductDraftPrRetryExecutor,
    verify_draft_pr_reauthorization,
)
from executor.draft_pr_effect import PreparedCommit


def _sha(payload):
    import hashlib

    return hashlib.sha256(canonical_effect_bytes(payload)).hexdigest()


class _Source:
    def __init__(self, payload):
        self.payload = payload

    def fetch_json(self, url):
        return self.payload


class _Transaction:
    calls = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        type(self).calls.append(kwargs)

    def execute(self, gateway):
        action = self.kwargs["action_kind"]
        return {
            "status": "EFFECT_COMPLETED_AND_OBSERVED",
            "action_kind": action,
            "object_id": "77" if action == "CREATE_PULL_REQUEST" else "a" * 40,
            "object_url": "https://github.com/FJ899/executor-pilot-target/pull/77",
        }


class ProductDraftPrRetryTests(unittest.TestCase):
    def setUp(self):
        self.contract_sha = "c" * 64
        self.run_id = "RUN-1"
        self.target = "FJ899/executor-pilot-target"
        self.branch = "executor-pilot/retry-1"
        self.old_effect_sha = "1" * 64
        self.old_result_sha = "2" * 64
        self.absence_sha = "3" * 64
        self.frozen = {
            "status": "AUTHORIZED_AND_FROZEN",
            "contract_sha256": self.contract_sha,
            "contract": {
                "request_evidence": {
                    "issue_number": 94,
                    "issue_node_id": "I_request_94",
                    "body_sha256": "b" * 64,
                },
                "decision_evidence": {
                    "created_at": "2026-08-26T22:45:30Z",
                    "expires_at": "2026-08-26T23:45:30Z",
                },
                "authority_boundary": {
                    "effect": "BOUNDED_DRAFT_PR_ONLY",
                    "merge": False,
                    "deploy": False,
                    "release": False,
                },
            },
        }
        self.pilot = {
            "status": "ACTION_COMPLETED_REVIEW_REQUIRED",
            "contract_sha256": self.contract_sha,
            "run_id": self.run_id,
            "repository": self.target,
            "source_commit": "4" * 40,
            "changed_paths": ["project_registry/registry.py"],
            "patch": {"sha256": "5" * 64},
            "draft_pr_request": {
                "draft": True,
                "merge_allowed": False,
                "title": "Executor bounded fix",
                "head_branch": self.branch,
                "body_evidence": {"run_id": self.run_id},
            },
        }
        prior_target = f"{self.target}@refs/heads/{self.branch}"
        self.prior = {
            "status": "DRAFT_PR_PUBLICATION_INCOMPLETE",
            "stage": "PUSH_DRAFT_BRANCH",
            "automatic_retry_allowed": False,
            "push": {
                "schema_version": "executor-github-effect-result/1.0",
                "status": "NO_EFFECT_CONFIRMED",
                "provider": "GITHUB",
                "action_kind": "CREATE_GIT_REF",
                "target": prior_target,
                "effect_sha256": self.old_effect_sha,
                "attempt_id": "ose-oldattempt",
                "absence_observation": {
                    "action_kind": "CREATE_GIT_REF",
                    "target": prior_target,
                    "attempt_id": "ose-oldattempt",
                    "effect_sha256": self.old_effect_sha,
                    "observed_at": "2026-08-26T23:03:56Z",
                    "complete": True,
                    "exists": False,
                    "evidence_sha256": self.absence_sha,
                },
                "automatic_retry_allowed": False,
                "next_attempt_requires_new_authority": True,
                "authority_result_binding": {
                    "authority_key": f"draft-pr:{self.contract_sha}:PUSH_DRAFT_BRANCH",
                    "payload_sha256": self.old_effect_sha,
                    "action_kind": "CREATE_GIT_REF",
                    "run_id": self.run_id,
                    "state": "FINAL",
                    "result_sha256": self.old_result_sha,
                    "binding_scope": "GLOBAL_AND_LOCAL_COMPOSITE",
                },
            },
        }
        self.prepared = PreparedCommit(
            repository=self.target,
            source_commit="4" * 40,
            commit_sha="a" * 40,
            tree_sha="d" * 40,
            head_branch=self.branch,
            patch_sha256="5" * 64,
            changed_paths=("project_registry/registry.py",),
        )
        push_payload = {
            "schema_version": "executor-git-ref-effect/1.0",
            "repository": self.target,
            "ref": f"refs/heads/{self.branch}",
            "sha": self.prepared.commit_sha,
        }
        pr_payload = {
            "schema_version": "executor-draft-pr-effect/1.0",
            "repository": self.target,
            "base": "main",
            "head": self.branch,
            "title": "Executor bounded fix",
            "body": "Executor bounded pilot result. Human review is required.",
            "draft": True,
        }
        self.plan = {
            "schema_version": "executor-draft-pr-retry-plan/1.0",
            "contract_sha256": self.contract_sha,
            "pilot_run_id": self.run_id,
            "prepared": self.prepared.__dict__,
            "push": {
                "action_kind": "CREATE_GIT_REF",
                "target": prior_target,
                "effect_sha256": _sha(push_payload),
                "payload": push_payload,
            },
            "pull_request": {
                "action_kind": "CREATE_PULL_REQUEST",
                "target": self.target,
                "effect_sha256": _sha(pr_payload),
                "payload": pr_payload,
            },
        }
        self.profile = GitHubTrustProfile(
            profile_id="github-product-gp001",
            intake_repository="FJ899/Executor",
            allowed_actor_login="FJ899",
            allowed_actor_id=275481581,
            allowed_target_repositories=(self.target,),
            max_decision_lifetime_seconds=3600,
        )

    def _reauth_payload(self):
        return {
            "schema_version": "executor-github-effect-reauthorization/1.0",
            "request": {
                "repository": "FJ899/Executor",
                "issue_number": 94,
                "issue_node_id": "I_request_94",
                "body_sha256": "b" * 64,
            },
            "contract_sha256": self.contract_sha,
            "pilot_run_id": self.run_id,
            "prior_no_effect": {
                "action_kind": "CREATE_GIT_REF",
                "target": self.prior["push"]["target"],
                "effect_sha256": self.old_effect_sha,
                "attempt_id": "ose-oldattempt",
                "result_sha256": self.old_result_sha,
                "absence_evidence_sha256": self.absence_sha,
            },
            "authorized_effects": {
                "push": {
                    "action_kind": "CREATE_GIT_REF",
                    "target": self.plan["push"]["target"],
                    "effect_sha256": self.plan["push"]["effect_sha256"],
                },
                "pull_request": {
                    "action_kind": "CREATE_PULL_REQUEST",
                    "target": self.target,
                    "effect_sha256": self.plan["pull_request"]["effect_sha256"],
                    "draft": True,
                },
                "merge": False,
                "deploy": False,
                "release": False,
                "tag": False,
            },
            "decision": "REAUTHORIZE_NO_EFFECT",
            "valid_for_seconds": 3600,
            "nonce": "human-effect-reauth-001",
        }

    def _source(self, payload=None):
        body = canonical_json(payload or self._reauth_payload())
        return _Source(
            {
                "url": "https://api.github.com/repos/FJ899/Executor/issues/comments/500",
                "issue_url": "https://api.github.com/repos/FJ899/Executor/issues/94",
                "id": 500,
                "node_id": "IC_reauth_500",
                "body": body,
                "created_at": "2026-08-26T23:06:30Z",
                "updated_at": "2026-08-26T23:06:30Z",
                "user": {"type": "User", "login": "FJ899", "id": 275481581},
                "author_association": "OWNER",
                "performed_via_github_app": None,
            }
        )

    def test_reauthorization_binds_exact_prior_no_effect_and_both_effects(self):
        verified = verify_draft_pr_reauthorization(
            self._source(),
            profile=self.profile,
            frozen_result=self.frozen,
            pilot_report=self.pilot,
            prior_publication=self.prior,
            retry_plan=self.plan,
            comment_id=500,
            now=datetime(2026, 8, 26, 23, 10, tzinfo=timezone.utc),
        )
        self.assertEqual(verified.comment_node_id, "IC_reauth_500")
        self.assertEqual(verified.push_effect_sha256, self.plan["push"]["effect_sha256"])
        self.assertEqual(
            verified.pull_request_effect_sha256,
            self.plan["pull_request"]["effect_sha256"],
        )

    def test_reauthorization_rejects_changed_prior_absence_binding(self):
        payload = self._reauth_payload()
        payload["prior_no_effect"]["absence_evidence_sha256"] = "9" * 64
        with self.assertRaises(DraftPrRetryError):
            verify_draft_pr_reauthorization(
                self._source(payload),
                profile=self.profile,
                frozen_result=self.frozen,
                pilot_report=self.pilot,
                prior_publication=self.prior,
                retry_plan=self.plan,
                comment_id=500,
                now=datetime(2026, 8, 26, 23, 10, tzinfo=timezone.utc),
            )

    def test_reauthorized_publish_uses_new_comment_bound_one_shot_keys(self):
        verified = verify_draft_pr_reauthorization(
            self._source(),
            profile=self.profile,
            frozen_result=self.frozen,
            pilot_report=self.pilot,
            prior_publication=self.prior,
            retry_plan=self.plan,
            comment_id=500,
            now=datetime(2026, 8, 26, 23, 10, tzinfo=timezone.utc),
        )
        _Transaction.calls = []
        with tempfile.TemporaryDirectory() as temp_name:
            workspace = Path(temp_name)
            executor = ProductDraftPrRetryExecutor(
                frozen_result=self.frozen,
                pilot_report=self.pilot,
                ledger=object(),
                evidence_directory=workspace / "evidence",
            )
            gateway = ProductGitHubDraftPrGateway(
                repository=self.target,
                workspace=workspace,
                token="secret-token",
            )
            with patch.object(executor, "prepare_commit", return_value=self.prepared), patch(
                "executor.product_draft_pr_retry.GitHubEffectTransaction", _Transaction
            ):
                result = executor.publish_reauthorized(
                    workspace=workspace,
                    prior_publication=self.prior,
                    retry_plan=self.plan,
                    reauthorization=verified,
                    gateway=gateway,
                )
        self.assertEqual(result["status"], "DRAFT_PR_CREATED_REVIEW_REQUIRED")
        self.assertEqual(len(_Transaction.calls), 2)
        prefix = f"draft-pr:{self.contract_sha}:REAUTH:IC_reauth_500:"
        self.assertEqual(_Transaction.calls[0]["authority_key"], prefix + "PUSH_DRAFT_BRANCH")
        self.assertEqual(_Transaction.calls[1]["authority_key"], prefix + "CREATE_DRAFT_PR")
        self.assertFalse(result["merge_allowed"])
        self.assertFalse(result["deploy_allowed"])
        self.assertFalse(result["release_allowed"])
        self.assertFalse(result["tag_allowed"])

    def test_git_token_is_env_only_and_uses_github_basic_token_identity(self):
        with tempfile.TemporaryDirectory() as temp_name:
            gateway = ProductGitHubDraftPrGateway(
                repository=self.target,
                workspace=temp_name,
                token="secret-token",
            )
            completed = subprocess.CompletedProcess([], 0, stdout="ok", stderr="")
            with patch("executor.product_draft_pr_gateway._git", return_value=completed) as mocked:
                result = gateway._git_push(sha="a" * 40, ref="refs/heads/test")
        self.assertEqual(result.provider_status, 200)
        args = mocked.call_args.args
        kwargs = mocked.call_args.kwargs
        self.assertNotIn("secret-token", " ".join(str(x) for x in args))
        self.assertIn("https://github.com/FJ899/executor-pilot-target.git", args)
        env = kwargs["env"]
        header = env["GIT_CONFIG_VALUE_0"]
        self.assertTrue(header.startswith("Authorization: Basic "))
        decoded = base64.b64decode(header.split()[-1]).decode("utf-8")
        self.assertEqual(decoded, "x-access-token:secret-token")
        self.assertEqual(
            env["GIT_CONFIG_KEY_0"], "http.https://github.com/.extraHeader"
        )


if __name__ == "__main__":
    unittest.main()
