from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.github_trust import canonical_json, verify_github_decision, verify_github_request
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


ROOT = Path(__file__).resolve().parents[1]


def canonical_gp001_task() -> dict:
    return json.loads(
        (ROOT / "tasks" / "GP001_FIX_FAILING_TEST_CASE_001.yaml").read_text(
            encoding="utf-8"
        )
    )


def governed_formation_draft(request_id: str) -> dict:
    user_request = "Napraw failing test dotyczący atomowości batcha."
    objective = "Naprawić regresję atomowości ProjectRegistry.add_many."
    return {
        "schema_version": "executor-contract-formation-draft/1.0",
        "executor_repository": "FJ899/Executor",
        "executor_commit": "e" * 40,
        "profile_id": "REQUEST_TO_CONTRACT_001",
        "profile_sha256": "a" * 64,
        "canonical_task_sha256": "b" * 64,
        "request_id": request_id,
        "draft_version": 1,
        "supersedes_draft_sha256": None,
        "user_request": user_request,
        "understood_objective": objective,
        "provenance": [
            {
                "path": "$.user_request",
                "source": "USER",
                "value": user_request,
                "note": "verbatim request supplied by the user",
            },
            {
                "path": "$.understood_objective",
                "source": "MODEL",
                "value": objective,
                "note": "interpretation proposal; not authoritative user intent",
            },
        ],
        "proposed_task_contract": canonical_gp001_task(),
        "out_of_scope_discoveries": [],
        "open_questions": [],
    }


def self_consistent_binding(draft: dict, payload: dict) -> tuple[str, dict]:
    authority_hash = hashlib.sha256(
        canonical_json(draft).encode("utf-8")
    ).hexdigest()
    binding = {
        "schema_version": "executor-contract-formation-binding/1.0",
        "executor_repository": draft["executor_repository"],
        "executor_commit": draft["executor_commit"],
        "formation_profile": draft["profile_id"],
        "formation_profile_sha256": draft["profile_sha256"],
        "canonical_task_sha256": draft["canonical_task_sha256"],
        "request_id": draft["request_id"],
        "draft_version": draft["draft_version"],
        "supersedes_draft_sha256": draft["supersedes_draft_sha256"],
        "draft_sha256": authority_hash,
        "draft": copy.deepcopy(draft),
        "authority_request_payload": copy.deepcopy(payload),
        "authority_request_payload_sha256": hashlib.sha256(
            canonical_json(payload).encode("utf-8")
        ).hexdigest(),
        "invalidated_draft_sha256s": [],
    }
    return authority_hash, binding


class FormationAuthorityBridgeTests(unittest.TestCase):
    def verified_custom_authority_hash(self, authority_hash: str):
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
        return source, request, draft, decision

    def test_custom_authority_hash_without_complete_formation_binding_fails_closed(self):
        authority_hash = "f" * 64
        source, _, draft, decision = self.verified_custom_authority_hash(authority_hash)
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
        payload = request_payload()
        formation_draft = governed_formation_draft(payload["request_id"])
        authority_hash, binding = self_consistent_binding(formation_draft, payload)
        binding["draft"]["understood_objective"] = "tampered after hashing"
        source, _, pilot_draft, decision = self.verified_custom_authority_hash(authority_hash)
        with tempfile.TemporaryDirectory() as directory:
            with patch("executor.pilot_contract._utc_now", return_value=NOW):
                with self.assertRaisesRegex(
                    PilotContractError,
                    "draft content hash mismatch",
                ):
                    apply_github_decision(
                        draft=pilot_draft,
                        decision=decision,
                        source=source,
                        profile=profile(),
                        ledger=governed_ledger(Path(directory) / "ledger.sqlite3"),
                        authority_draft_sha256=authority_hash,
                        expected_request_payload=payload,
                        formation_binding=binding,
                    )

    def test_self_consistent_forged_request_not_derived_from_formation_draft_is_blocked(self):
        forged_payload = request_payload()
        formation_draft = governed_formation_draft(forged_payload["request_id"])
        authority_hash, binding = self_consistent_binding(
            formation_draft,
            forged_payload,
        )
        source, _, pilot_draft, decision = self.verified_custom_authority_hash(authority_hash)

        # The draft/hash/binding/request payload are mutually self-consistent, and the
        # human decision is valid for that draft hash. The payload is still unrelated
        # to the GP001 target/scope encoded in proposed_task_contract and must fail.
        with tempfile.TemporaryDirectory() as directory:
            with patch("executor.pilot_contract._utc_now", return_value=NOW):
                with self.assertRaisesRegex(
                    PilotContractError,
                    "does not match governed formation draft projection",
                ):
                    apply_github_decision(
                        draft=pilot_draft,
                        decision=decision,
                        source=source,
                        profile=profile(),
                        ledger=governed_ledger(Path(directory) / "ledger.sqlite3"),
                        authority_draft_sha256=authority_hash,
                        expected_request_payload=forged_payload,
                        formation_binding=binding,
                    )


if __name__ == "__main__":
    unittest.main()
