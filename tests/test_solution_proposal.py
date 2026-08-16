from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from executor.github_trust import verify_github_decision, verify_github_request
from executor.pilot_contract import (
    apply_github_decision,
    build_pilot_draft,
    pilot_draft_sha256,
)
from executor.solution_proposal import (
    SolutionProposalError,
    materialize_solution_candidate,
    validate_solution_proposal,
)
from tests.p4_test_support import governed_ledger, provenance_for
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
)


def frozen_result():
    from tests.test_github_trust import request_payload

    payload = request_payload()
    source = FakeSource(
        {
            ISSUE_URL: issue(json.dumps(payload, sort_keys=True)),
            commit_url(payload): commit_evidence(payload),
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
    temp = tempfile.TemporaryDirectory()
    result = apply_github_decision(
        draft=draft,
        decision=decision,
        ledger=governed_ledger(Path(temp.name) / "ledger.sqlite3"),
    )
    return temp, result


def proposal(result):
    replacement = "VALUE = 2\n"
    return {
        "schema_version": "executor-solution-proposal/1.0",
        "proposal_id": "proposal-001",
        "contract_sha256": result["contract_sha256"],
        "repository": result["contract"]["target"]["repository"],
        "source_commit": result["contract"]["target"]["commit"],
        "source_tree": result["contract"]["target"]["tree"],
        "mutations": [
            {
                "path": "phase6/scriptops-v2-hardening.py",
                "expected_before_sha256": "c" * 64,
                "replacement_text": replacement,
                "expected_after_sha256": hashlib.sha256(
                    replacement.encode()
                ).hexdigest(),
            }
        ],
        "rationale": "Fix the observed numeric ordering counterexample.",
        "evidence_plan": [
            ["python", "-c", "raise SystemExit(0)"],
            ["python", "-m", "unittest", "discover", "-s", "tests"],
        ],
        "provenance": provenance_for(result),
    }


class SolutionProposalTests(unittest.TestCase):
    def test_external_proposal_is_bounded_and_has_no_authority(self):
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        validated = validate_solution_proposal(proposal(frozen), frozen_result=frozen)
        self.assertEqual(len(validated.mutations), 1)
        self.assertEqual(validated.repository, "JTJ07/scriptops")
        self.assertEqual(validated.provenance["producer_role"], "EXTERNAL_INTELLIGENCE")
        self.assertEqual(validated.provenance["human_solution_edits"], 0)
        self.assertEqual(validated.provenance["effect_capability"], "NONE")

    def test_proposal_cannot_smuggle_authority(self):
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        candidate = proposal(frozen)
        candidate["authority"] = {"decision": "ALLOW"}
        with self.assertRaises(SolutionProposalError):
            validate_solution_proposal(candidate, frozen_result=frozen)

    def test_missing_or_pre_request_provenance_blocks(self):
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        missing = proposal(frozen)
        missing.pop("provenance")
        with self.assertRaises(SolutionProposalError):
            validate_solution_proposal(missing, frozen_result=frozen)
        predates = proposal(frozen)
        predates["provenance"]["generated_at"] = "2026-08-15T23:59:59Z"
        with self.assertRaisesRegex(SolutionProposalError, "predates"):
            validate_solution_proposal(predates, frozen_result=frozen)

    def test_wrong_contract_scope_or_after_hash_blocks(self):
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        for change in ("contract", "scope", "hash", "request-provenance"):
            with self.subTest(change=change):
                candidate = copy.deepcopy(proposal(frozen))
                if change == "contract":
                    candidate["contract_sha256"] = "d" * 64
                elif change == "scope":
                    candidate["mutations"][0]["path"] = "tests/test_escape.py"
                elif change == "hash":
                    candidate["mutations"][0]["expected_after_sha256"] = "e" * 64
                else:
                    candidate["provenance"]["request"]["body_sha256"] = "e" * 64
                with self.assertRaises(SolutionProposalError):
                    validate_solution_proposal(candidate, frozen_result=frozen)

    def test_candidate_materializes_only_with_separate_exact_provenance(self):
        temp, frozen = frozen_result()
        self.addCleanup(temp.cleanup)
        complete = proposal(frozen)
        candidate = {
            key: copy.deepcopy(value)
            for key, value in complete.items()
            if key not in {"schema_version", "contract_sha256", "provenance"}
        }
        candidate["schema_version"] = "executor-solution-candidate/1.0"
        candidate["status"] = "AWAITING_FROZEN_CONTRACT_SHA"
        materialized = materialize_solution_candidate(
            candidate,
            frozen_result=frozen,
            provenance=provenance_for(frozen),
        )
        self.assertEqual(materialized["contract_sha256"], frozen["contract_sha256"])
        self.assertEqual(materialized["provenance"]["producer_role"], "EXTERNAL_INTELLIGENCE")
        self.assertNotIn("status", materialized)


if __name__ == "__main__":
    unittest.main()
