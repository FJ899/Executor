from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.github_trust import GitHubTrustError, verify_github_request
from executor.pilot_contract import build_pilot_draft_from_formation, pilot_draft_sha256
from executor.product_frozen_authority import validate_product_frozen_pilot_authority
from executor.product_github_authority import (
    apply_product_github_decision,
    verify_formation_published_request,
    verify_product_github_decision,
)
from tests.p4_test_support import governed_ledger
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
from tests.test_product_authority_transport import formation_request, publication


def system_issue(payload: dict) -> dict:
    value = issue(json.dumps(payload, sort_keys=True))
    value["author_association"] = "NONE"
    value["performed_via_github_app"] = {"id": 15368, "slug": "github-actions"}
    value["user"] = {
        "login": "github-actions[bot]",
        "id": 41898282,
        "type": "Bot",
    }
    return value


class ProductSystemTransportAuthorityTests(unittest.TestCase):
    def verified_system_request(self):
        payload = request_payload()
        values = {
            ISSUE_URL: system_issue(payload),
            commit_url(payload): commit_evidence(payload),
        }
        source = FakeSource(values)
        request = verify_formation_published_request(
            source,
            profile=profile(),
            issue_number=61,
            expected_payload=payload,
            now=NOW,
        )
        return source, request

    def product_material(self):
        source, request = self.verified_system_request()
        formation = formation_request(request)
        transport = publication(request, formation)
        draft = build_pilot_draft_from_formation(
            formation,
            request,
            formation_publication=transport,
        )
        draft_sha = pilot_draft_sha256(draft)
        source.values[COMMENT_URL] = comment(decision_payload(request, draft_sha))
        decision = verify_product_github_decision(
            source,
            profile=profile(),
            request=request,
            comment_id=9001,
            draft_sha256=draft_sha,
            now=NOW,
        )
        return source, request, formation, transport, draft, decision

    def test_system_issue_is_transport_even_when_legacy_direct_human_verifier_rejects_it(self) -> None:
        payload = request_payload()
        source = FakeSource(
            {
                ISSUE_URL: system_issue(payload),
                commit_url(payload): commit_evidence(payload),
            }
        )
        request = verify_formation_published_request(
            source,
            profile=profile(),
            issue_number=61,
            expected_payload=payload,
            now=NOW,
        )
        self.assertEqual(request.actor_login, "github-actions[bot]")
        with self.assertRaises(GitHubTrustError):
            verify_github_request(source, profile=profile(), issue_number=61, now=NOW)

    def test_human_decision_does_not_have_to_match_system_transport_actor(self) -> None:
        _, request, _, _, _, decision = self.product_material()
        self.assertEqual(request.actor_login, "github-actions[bot]")
        self.assertEqual(decision.actor_login, "FJ899")
        self.assertEqual(decision.decision, "ACCEPT")

    def test_app_mediated_decision_still_blocks(self) -> None:
        source, request = self.verified_system_request()
        formation = formation_request(request)
        transport = publication(request, formation)
        draft = build_pilot_draft_from_formation(
            formation,
            request,
            formation_publication=transport,
        )
        draft_sha = pilot_draft_sha256(draft)
        mediated = comment(decision_payload(request, draft_sha))
        mediated["performed_via_github_app"] = {"id": 15368, "slug": "github-actions"}
        source.values[COMMENT_URL] = mediated
        with self.assertRaisesRegex(GitHubTrustError, "app-mediated"):
            verify_product_github_decision(
                source,
                profile=profile(),
                request=request,
                comment_id=9001,
                draft_sha256=draft_sha,
                now=NOW,
            )

    def test_product_accept_freezes_and_validates_with_system_request_transport(self) -> None:
        source, request, formation, transport, draft, decision = self.product_material()
        with tempfile.TemporaryDirectory() as directory:
            with patch("executor.product_github_authority._utc_now", return_value=NOW):
                frozen = apply_product_github_decision(
                    draft=draft,
                    decision=decision,
                    source=source,
                    profile=profile(),
                    ledger=governed_ledger(Path(directory) / "authority.sqlite3", shared={}),
                    formation_request=formation,
                    formation_publication=transport,
                )
            self.assertEqual(frozen["status"], "AUTHORIZED_AND_FROZEN")
            self.assertTrue(frozen["executable"])
            request_authority, decision_authority = validate_product_frozen_pilot_authority(frozen)
            self.assertEqual(request_authority.body_sha256, request.body_sha256)
            self.assertEqual(decision_authority.actor_login, "FJ899")
            self.assertEqual(decision_authority.decision, "ACCEPT")

    def test_transport_authority_escalation_breaks_frozen_validation(self) -> None:
        source, _, formation, transport, draft, decision = self.product_material()
        with tempfile.TemporaryDirectory() as directory:
            with patch("executor.product_github_authority._utc_now", return_value=NOW):
                frozen = apply_product_github_decision(
                    draft=draft,
                    decision=decision,
                    source=source,
                    profile=profile(),
                    ledger=governed_ledger(Path(directory) / "authority.sqlite3", shared={}),
                    formation_request=formation,
                    formation_publication=transport,
                )
            forged = copy.deepcopy(frozen)
            forged["contract"]["request_transport_provenance"]["authority"] = True
            with self.assertRaises(Exception):
                validate_product_frozen_pilot_authority(forged)


if __name__ == "__main__":
    unittest.main()
