from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.draft_pr_effect import (
    DraftPrEffectError,
    DraftPrEffectExecutor,
    PreparedCommit,
)


class _Gateway:
    def __init__(self, repository: str, workspace: Path) -> None:
        self.repository = repository
        self.workspace = workspace.resolve()
        self.payloads = []

    def bind_effect_payload(self, payload):
        self.payloads.append(payload)


class _Transaction:
    calls = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        type(self).calls.append(kwargs)

    def execute(self, gateway):
        action = self.kwargs["action_kind"]
        return {
            "status": "EFFECT_COMPLETED_AND_OBSERVED",
            "action_kind": action,
            "object_id": "123" if action == "CREATE_PULL_REQUEST" else "a" * 40,
            "object_url": "https://github.com/FJ899/executor-pilot-target/pull/123",
        }


class DraftPrEffectExecutorTests(unittest.TestCase):
    def frozen(self):
        return {
            "status": "AUTHORIZED_AND_FROZEN",
            "contract_sha256": "c" * 64,
            "contract": {
                "authority_boundary": {
                    "effect": "BOUNDED_DRAFT_PR_ONLY",
                    "merge": False,
                    "deploy": False,
                    "release": False,
                },
                "decision_evidence": {"expires_at": "2099-01-01T00:00:00Z"},
            },
        }

    def report(self):
        return {
            "status": "ACTION_COMPLETED_REVIEW_REQUIRED",
            "contract_sha256": "c" * 64,
            "run_id": "RUN-1",
            "repository": "FJ899/executor-pilot-target",
            "source_commit": "1" * 40,
            "changed_paths": ["src/fix.py"],
            "draft_pr_request": {
                "draft": True,
                "merge_allowed": False,
                "title": "Executor bounded fix",
                "head_branch": "executor/bounded-fix",
                "body_evidence": {"run_id": "RUN-1"},
            },
        }

    def test_publication_requires_frozen_accept(self) -> None:
        frozen = self.frozen()
        frozen["status"] = "MODIFICATION_REQUIRED"
        with self.assertRaisesRegex(DraftPrEffectError, "requires a frozen ACCEPT"):
            DraftPrEffectExecutor(
                frozen_result=frozen,
                pilot_report=self.report(),
                ledger=object(),
                evidence_directory="evidence",
            )

    def test_publication_requires_draft_only_boundary(self) -> None:
        frozen = self.frozen()
        frozen["contract"]["authority_boundary"]["merge"] = True
        with self.assertRaisesRegex(DraftPrEffectError, "does not permit bounded draft PR publication"):
            DraftPrEffectExecutor(
                frozen_result=frozen,
                pilot_report=self.report(),
                ledger=object(),
                evidence_directory="evidence",
            )

    def test_publish_uses_contract_bound_one_shot_push_and_pr_keys(self) -> None:
        _Transaction.calls = []
        with tempfile.TemporaryDirectory() as temp_name:
            workspace = Path(temp_name)
            executor = DraftPrEffectExecutor(
                frozen_result=self.frozen(),
                pilot_report=self.report(),
                ledger=object(),
                evidence_directory=workspace / "evidence",
            )
            prepared = PreparedCommit(
                repository="FJ899/executor-pilot-target",
                source_commit="1" * 40,
                commit_sha="2" * 40,
                tree_sha="3" * 40,
                head_branch="executor/bounded-fix",
                patch_sha256="4" * 64,
                changed_paths=("src/fix.py",),
            )
            gateway = _Gateway(prepared.repository, workspace)
            with patch.object(executor, "prepare_commit", return_value=prepared), patch(
                "executor.draft_pr_effect.GitHubEffectTransaction",
                _Transaction,
            ):
                result = executor.publish(workspace=workspace, gateway=gateway)

        self.assertEqual(result["status"], "DRAFT_PR_CREATED_REVIEW_REQUIRED")
        self.assertTrue(result["human_review_required"])
        self.assertEqual(result["human_acceptance"], "PENDING")
        self.assertFalse(result["merge_allowed"])
        self.assertFalse(result["deploy_allowed"])
        self.assertFalse(result["release_allowed"])
        self.assertFalse(result["tag_allowed"])
        self.assertEqual(len(_Transaction.calls), 2)
        self.assertEqual(
            _Transaction.calls[0]["authority_key"],
            "draft-pr:" + "c" * 64 + ":PUSH_DRAFT_BRANCH",
        )
        self.assertEqual(_Transaction.calls[0]["action_kind"], "CREATE_GIT_REF")
        self.assertEqual(
            _Transaction.calls[1]["authority_key"],
            "draft-pr:" + "c" * 64 + ":CREATE_DRAFT_PR",
        )
        self.assertEqual(_Transaction.calls[1]["action_kind"], "CREATE_PULL_REQUEST")
        self.assertEqual(_Transaction.calls[0]["run_id"], "RUN-1")
        self.assertEqual(_Transaction.calls[1]["run_id"], "RUN-1")


if __name__ == "__main__":
    unittest.main()
