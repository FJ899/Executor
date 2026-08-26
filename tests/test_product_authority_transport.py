from __future__ import annotations

import copy
import unittest

from executor.pilot_contract import (
    PilotContractError,
    _validated_formation_publication,
    build_pilot_draft_from_formation,
)


class FakeVerifiedRequest:
    repository = "FJ899/Executor"
    issue_number = 42
    issue_id = 4200
    issue_node_id = "I_PRODUCT_42"
    actor_login = "FJ899"
    actor_id = 275481581
    body_sha256 = "a" * 64
    created_at = "2026-08-26T18:00:00Z"
    observed_at = "2026-08-26T18:01:00Z"

    def __init__(self) -> None:
        self.payload = {
            "schema_version": "executor-github-request/1.0",
            "request_id": "request-product-42",
            "target": {
                "repository": "FJ899/executor-pilot-target",
                "commit": "1" * 40,
                "tree": "2" * 40,
            },
            "task": {
                "class": "BOUNDED_CORRECTNESS_OR_QUALITY_FIX",
                "problem_statement": "Fix bounded failing test",
                "allowed_paths": ["project_registry/registry.py"],
                "protected_paths": ["tests/**"],
                "precondition_argv": [["python", "-m", "unittest", "tests.test_registry"]],
                "postcondition_argv": [["python", "-m", "unittest", "tests.test_registry"]],
                "regression_argv": [["python", "-m", "unittest", "discover", "-s", "tests"]],
                "max_production_files": 1,
                "max_patch_lines": 100,
            },
            "expires_at": "2026-08-26T19:00:00Z",
            "nonce": "nonce-product-42",
        }

    @property
    def evidence_ref(self) -> str:
        return f"github:issue:{self.issue_node_id}:{self.body_sha256}"

    def to_dict(self) -> dict:
        return {
            "provider": "GITHUB",
            "profile_id": "GITHUB-PRODUCT-GP001-001",
            "repository": self.repository,
            "issue_number": self.issue_number,
            "issue_id": self.issue_id,
            "issue_node_id": self.issue_node_id,
            "actor": {"login": self.actor_login, "id": self.actor_id},
            "body_sha256": self.body_sha256,
            "created_at": self.created_at,
            "observed_at": self.observed_at,
            "evidence_ref": self.evidence_ref,
        }


def formation_request(request: FakeVerifiedRequest) -> dict:
    return {
        "schema_version": "executor-canonical-contract-request/1.0",
        "status": "AWAITING_VERIFIED_HUMAN_AUTHORIZATION",
        "executable": False,
        "github_request_payload": copy.deepcopy(request.payload),
        "formation_binding": {
            "executor_repository": "FJ899/Executor",
            "executor_commit": "3" * 40,
            "formation_profile": "REQUEST_TO_CONTRACT_001",
            "formation_profile_sha256": "4" * 64,
            "canonical_task_sha256": "5" * 64,
            "draft_sha256": "6" * 64,
        },
    }


def publication(request: FakeVerifiedRequest, formation: dict) -> dict:
    effect = {
        "schema_version": "executor-github-effect-result/1.0",
        "status": "EFFECT_COMPLETED_AND_OBSERVED",
        "provider": "GITHUB",
        "action_kind": "CREATE_ISSUE",
        "target": request.repository,
        "effect_sha256": "7" * 64,
        "attempt_id": "ose-" + "8" * 32,
        "object_id": str(request.issue_number),
        "object_url": f"https://github.com/{request.repository}/issues/{request.issue_number}",
        "observation_ref": "/tmp/observation.json",
        "automatic_retry_allowed": False,
        "original_success_receipt": "PRESENT",
    }
    transport = {
        "origin": "FORMATION_PUBLISHED_REQUEST",
        "authority": False,
        "publisher": "EXECUTOR_FORMATION",
        "provider": "GITHUB",
        "action_kind": "CREATE_ISSUE",
        "target": request.repository,
        "object_id": effect["object_id"],
        "object_url": effect["object_url"],
        "effect_sha256": effect["effect_sha256"],
        "observation_ref": effect["observation_ref"],
        "human_decision_required": True,
    }
    return {
        "schema_version": "executor-formation-publication-result/1.1",
        "status": "AWAITING_VERIFIED_HUMAN_DECISION",
        "canonical_contract_request": copy.deepcopy(formation),
        "formation_binding": copy.deepcopy(formation["formation_binding"]),
        "github_request_payload": copy.deepcopy(request.payload),
        "request_transport_provenance": transport,
        "publication_effect": effect,
        "manual_request_rewrite_required": False,
        "executable": False,
    }


class ProductAuthorityTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = FakeVerifiedRequest()
        self.formation = formation_request(self.request)
        self.publication = publication(self.request, self.formation)

    def test_publication_transport_is_bound_and_non_authoritative(self) -> None:
        provenance = _validated_formation_publication(
            self.publication,
            formation_request=self.formation,
            request=self.request,
        )
        self.assertEqual(provenance["origin"], "FORMATION_PUBLISHED_REQUEST")
        self.assertFalse(provenance["authority"])
        self.assertTrue(provenance["human_decision_required"])

    def test_draft_explicitly_separates_transport_from_human_authority(self) -> None:
        draft = build_pilot_draft_from_formation(
            self.formation,
            self.request,
            formation_publication=self.publication,
        )
        self.assertEqual(draft["schema_version"], "executor-pilot-draft/1.2")
        self.assertFalse(draft["authority_boundary"]["request_transport_is_authority"])
        self.assertTrue(draft["authority_boundary"]["human_decision_is_authority"])
        self.assertEqual(
            draft["request_transport_provenance"]["object_id"],
            str(self.request.issue_number),
        )

    def test_different_issue_cannot_be_substituted(self) -> None:
        forged = copy.deepcopy(self.publication)
        forged["publication_effect"]["object_id"] = "99"
        forged["request_transport_provenance"]["object_id"] = "99"
        with self.assertRaisesRegex(PilotContractError, "published issue"):
            _validated_formation_publication(
                forged,
                formation_request=self.formation,
                request=self.request,
            )

    def test_transport_cannot_claim_human_authority(self) -> None:
        forged = copy.deepcopy(self.publication)
        forged["request_transport_provenance"]["authority"] = True
        with self.assertRaisesRegex(PilotContractError, "zero human authority"):
            _validated_formation_publication(
                forged,
                formation_request=self.formation,
                request=self.request,
            )

    def test_manual_request_rewrite_is_rejected(self) -> None:
        forged = copy.deepcopy(self.publication)
        forged["manual_request_rewrite_required"] = True
        with self.assertRaisesRegex(PilotContractError, "missing or incomplete"):
            _validated_formation_publication(
                forged,
                formation_request=self.formation,
                request=self.request,
            )


if __name__ == "__main__":
    unittest.main()
