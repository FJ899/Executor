from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from executor.draft_pr_effect import PreparedCommit
from executor.github_effect_transaction import canonical_effect_bytes
from executor.github_trust import GitHubTrustProfile, canonical_json
from executor.product_draft_pr_gateway import ProductGitHubDraftPrGateway
from executor.product_draft_pr_retry import (
    ProductDraftPrRetryExecutor,
    verify_draft_pr_reauthorization,
)


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


class DraftPrRetryJsonRoundTripTests(unittest.TestCase):
    def test_json_round_trip_does_not_change_prepared_commit_identity(self):
        contract_sha = "c" * 64
        run_id = "RUN-JSON-ROUNDTRIP"
        target = "FJ899/executor-pilot-target"
        branch = "executor-pilot/retry-json-roundtrip"
        prepared = PreparedCommit(
            repository=target,
            source_commit="4" * 40,
            commit_sha="a" * 40,
            tree_sha="d" * 40,
            head_branch=branch,
            patch_sha256="5" * 64,
            changed_paths=("project_registry/registry.py",),
        )
        frozen = {
            "status": "AUTHORIZED_AND_FROZEN",
            "contract_sha256": contract_sha,
            "contract": {
                "request_evidence": {
                    "issue_number": 97,
                    "issue_node_id": "I_request_97",
                    "body_sha256": "b" * 64,
                },
                "decision_evidence": {
                    "created_at": "2026-08-27T07:00:00Z",
                    "expires_at": "2026-08-27T08:00:00Z",
                },
                "authority_boundary": {
                    "effect": "BOUNDED_DRAFT_PR_ONLY",
                    "merge": False,
                    "deploy": False,
                    "release": False,
                },
            },
        }
        report = {
            "status": "ACTION_COMPLETED_REVIEW_REQUIRED",
            "contract_sha256": contract_sha,
            "run_id": run_id,
            "repository": target,
            "source_commit": prepared.source_commit,
            "changed_paths": list(prepared.changed_paths),
            "patch": {"sha256": prepared.patch_sha256},
            "draft_pr_request": {
                "draft": True,
                "merge_allowed": False,
                "title": "Executor bounded fix",
                "head_branch": branch,
                "body_evidence": {"run_id": run_id},
            },
        }
        prior_target = f"{target}@refs/heads/{branch}"
        prior = {
            "status": "DRAFT_PR_PUBLICATION_INCOMPLETE",
            "stage": "PUSH_DRAFT_BRANCH",
            "automatic_retry_allowed": False,
            "push": {
                "schema_version": "executor-github-effect-result/1.0",
                "status": "NO_EFFECT_CONFIRMED",
                "provider": "GITHUB",
                "action_kind": "CREATE_GIT_REF",
                "target": prior_target,
                "effect_sha256": "1" * 64,
                "attempt_id": "ose-prior-json-roundtrip",
                "absence_observation": {
                    "action_kind": "CREATE_GIT_REF",
                    "target": prior_target,
                    "attempt_id": "ose-prior-json-roundtrip",
                    "effect_sha256": "1" * 64,
                    "observed_at": "2026-08-27T07:01:00Z",
                    "complete": True,
                    "exists": False,
                    "evidence_sha256": "3" * 64,
                },
                "automatic_retry_allowed": False,
                "next_attempt_requires_new_authority": True,
                "authority_result_binding": {
                    "authority_key": f"draft-pr:{contract_sha}:PUSH_DRAFT_BRANCH",
                    "payload_sha256": "1" * 64,
                    "action_kind": "CREATE_GIT_REF",
                    "run_id": run_id,
                    "state": "FINAL",
                    "result_sha256": "2" * 64,
                    "binding_scope": "GLOBAL_AND_LOCAL_COMPOSITE",
                },
            },
        }
        push_payload = {
            "schema_version": "executor-git-ref-effect/1.0",
            "repository": target,
            "ref": f"refs/heads/{branch}",
            "sha": prepared.commit_sha,
        }
        pr_payload = {
            "schema_version": "executor-draft-pr-effect/1.0",
            "repository": target,
            "base": "main",
            "head": branch,
            "title": "Executor bounded fix",
            "body": "Executor bounded pilot result. Human review is required.",
            "draft": True,
        }
        plan = {
            "schema_version": "executor-draft-pr-retry-plan/1.0",
            "contract_sha256": contract_sha,
            "pilot_run_id": run_id,
            "prepared": prepared.__dict__,
            "push": {
                "action_kind": "CREATE_GIT_REF",
                "target": prior_target,
                "effect_sha256": _sha(push_payload),
                "payload": push_payload,
            },
            "pull_request": {
                "action_kind": "CREATE_PULL_REQUEST",
                "target": target,
                "effect_sha256": _sha(pr_payload),
                "payload": pr_payload,
            },
        }
        round_tripped_plan = json.loads(json.dumps(plan))
        self.assertIsInstance(round_tripped_plan["prepared"]["changed_paths"], list)

        reauth_payload = {
            "schema_version": "executor-github-effect-reauthorization/1.0",
            "request": {
                "repository": "FJ899/Executor",
                "issue_number": 97,
                "issue_node_id": "I_request_97",
                "body_sha256": "b" * 64,
            },
            "contract_sha256": contract_sha,
            "pilot_run_id": run_id,
            "prior_no_effect": {
                "action_kind": "CREATE_GIT_REF",
                "target": prior_target,
                "effect_sha256": "1" * 64,
                "attempt_id": "ose-prior-json-roundtrip",
                "result_sha256": "2" * 64,
                "absence_evidence_sha256": "3" * 64,
            },
            "authorized_effects": {
                "push": {
                    "action_kind": "CREATE_GIT_REF",
                    "target": prior_target,
                    "effect_sha256": round_tripped_plan["push"]["effect_sha256"],
                },
                "pull_request": {
                    "action_kind": "CREATE_PULL_REQUEST",
                    "target": target,
                    "effect_sha256": round_tripped_plan["pull_request"]["effect_sha256"],
                    "draft": True,
                },
                "merge": False,
                "deploy": False,
                "release": False,
                "tag": False,
            },
            "decision": "REAUTHORIZE_NO_EFFECT",
            "valid_for_seconds": 3600,
            "nonce": "human-json-roundtrip-001",
        }
        source = _Source(
            {
                "url": "https://api.github.com/repos/FJ899/Executor/issues/comments/500",
                "issue_url": "https://api.github.com/repos/FJ899/Executor/issues/97",
                "id": 500,
                "node_id": "IC_json_roundtrip_500",
                "body": canonical_json(reauth_payload),
                "created_at": "2026-08-27T07:02:00Z",
                "updated_at": "2026-08-27T07:02:00Z",
                "user": {"type": "User", "login": "FJ899", "id": 275481581},
                "author_association": "OWNER",
                "performed_via_github_app": None,
            }
        )
        profile = GitHubTrustProfile(
            profile_id="github-product-gp001",
            intake_repository="FJ899/Executor",
            allowed_actor_login="FJ899",
            allowed_actor_id=275481581,
            allowed_target_repositories=(target,),
            max_decision_lifetime_seconds=3600,
        )
        verified = verify_draft_pr_reauthorization(
            source,
            profile=profile,
            frozen_result=frozen,
            pilot_report=report,
            prior_publication=prior,
            retry_plan=round_tripped_plan,
            comment_id=500,
            now=datetime(2026, 8, 27, 7, 3, tzinfo=timezone.utc),
        )

        _Transaction.calls = []
        with tempfile.TemporaryDirectory() as temp_name:
            workspace = Path(temp_name)
            executor = ProductDraftPrRetryExecutor(
                frozen_result=frozen,
                pilot_report=report,
                ledger=object(),
                evidence_directory=workspace / "evidence",
            )
            gateway = ProductGitHubDraftPrGateway(
                repository=target,
                workspace=workspace,
                token="secret-token",
            )
            with patch.object(executor, "prepare_commit", return_value=prepared), patch(
                "executor.product_draft_pr_retry.GitHubEffectTransaction", _Transaction
            ):
                result = executor.publish_reauthorized(
                    workspace=workspace,
                    prior_publication=prior,
                    retry_plan=round_tripped_plan,
                    reauthorization=verified,
                    gateway=gateway,
                )

        self.assertEqual(result["status"], "DRAFT_PR_CREATED_REVIEW_REQUIRED")
        self.assertEqual(result["prepared"]["changed_paths"], ["project_registry/registry.py"])
        self.assertEqual(len(_Transaction.calls), 2)


if __name__ == "__main__":
    unittest.main()
