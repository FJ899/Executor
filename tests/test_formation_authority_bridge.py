from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.github_trust import verify_github_decision, verify_github_request
from executor.pilot_contract import (
    PilotContractError,
    apply_github_decision,
    build_pilot_draft,
)
from tests.p4_test_support import governed_ledger
from tests.test_github_trust import (
    COMMENT_URL,
    NOW,
    FakeSource,
    comment,
    commit_evidence,
    commit_url,
    decision_payload,
    issue,
    profile,
    request_payload,
)


class FormationAuthorityBridgeTests(unittest.TestCase):
    def verified_custom_authority_hash(self):
        payload = request_payload()
        source = FakeSource(
            {
                commit_url(payload): commit_evidence(payload),
                f"https://api.github.com/repos/FJ899/Executor/issues/61": issue(),
            }
        )
        request = verify_github_request(
            source,
            profile=profile(),
            issue_number=61,
            now=NOW,
        )
        draft = build_pilot_draft(request)
        authority_hash = "f" * 64
        source.values[COMMENT_URL] = comment(
            decision_payload(request, authority_hash, "ACCEPT")
        )
        decision = verify_github_decision(
            source,
            profile=profile(),
            request=request,
            comment_id=9001,
            draft_sha256=authority_hash,
            now=NOW,
        )
        return source, request, draft, decision, authority_hash

    def test_custom_authority_hash_without_complete_formation_binding_fails_closed(self):
        source, _, draft, decision, authority_hash = self.verified_custom_authority_hash()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                PilotContractError,
                "requires draft hash, request payload and binding",
            ):
                apply_github_decision(
                    draft=draft,
                    decision=decision,
                    source=source,
                    profile=profile(),
                    ledger=governed_ledger(Path(directory) / "ledger.sqlite3"),
                    authority_draft_sha256=authority_hash,
                )

    def test_tampered_formation_draft_content_cannot_back_custom_authority_hash(self):
        source, request, draft, decision, authority_hash = self.verified_custom_authority_hash()
        binding = {
            "schema_version": "executor-contract-formation-binding/1.0",
            "executor_repository": "FJ899/Executor",
            "executor_commit": "e" * 40,
            "formation_profile": "REQUEST_TO_CONTRACT_001",
            "formation_profile_sha256": "a" * 64,
            "canonical_task_sha256": "b" * 64,
            "request_id": request.payload["request_id"],
            "draft_version": 1,
            "supersedes_draft_sha256": None,
            "draft_sha256": authority_hash,
            "draft": {
                "request_id": request.payload["request_id"],
                "draft_version": 1,
                "supersedes_draft_sha256": None,
            },
            "authority_request_payload": request.payload,
            "authority_request_payload_sha256": "0" * 64,
            "invalidated_draft_sha256s": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            with patch("executor.pilot_contract._utc_now", return_value=NOW):
                with self.assertRaisesRegex(
                    PilotContractError,
                    "draft content hash mismatch",
                ):
                    apply_github_decision(
                        draft=draft,
                        decision=decision,
                        source=source,
                        profile=profile(),
                        ledger=governed_ledger(Path(directory) / "ledger.sqlite3"),
                        authority_draft_sha256=authority_hash,
                        expected_request_payload=request.payload,
                        formation_binding=binding,
                    )


if __name__ == "__main__":
    unittest.main()
