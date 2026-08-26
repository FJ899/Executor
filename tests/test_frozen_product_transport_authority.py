from __future__ import annotations

import copy
import hashlib
import unittest

from executor.frozen_pilot_authority import (
    AUTHORITY_SNAPSHOT_SCHEMA,
    REVOCATION_CUTOFF,
    FrozenPilotAuthorityError,
    authority_snapshot_sha256,
    validate_frozen_pilot_authority,
)
from executor.github_trust import canonical_json


REPO = "FJ899/Executor"
TARGET_REPO = "FJ899/executor-pilot-target"
ISSUE = 94
ISSUE_ID = 9400
ISSUE_NODE = "I_product_transport_test"
COMMENT_ID = 5431977112
COMMENT_NODE = "IC_product_accept005_test"
HUMAN_LOGIN = "FJ899"
HUMAN_ID = 275481581
DRAFT_SHA = "d" * 64
TARGET_COMMIT = "a" * 40
TARGET_TREE = "b" * 40
REQUEST_EXPIRES = "2026-08-26T23:40:48Z"
DECISION_CREATED = "2026-08-26T22:45:30Z"
DECISION_EXPIRES = "2026-08-26T23:45:30Z"
VERIFIED_AT = "2026-08-26T22:57:30Z"
PROVIDER_CREATED_AT = "2026-08-26T22:57:31Z"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _finalize_receipts(result: dict) -> dict:
    snapshot = result["contract"]["authority_snapshot"]
    snapshot_sha = authority_snapshot_sha256(snapshot)
    result["contract"]["authority_snapshot_sha256"] = snapshot_sha
    result["authority_snapshot_sha256"] = snapshot_sha
    result["contract"]["authority_snapshot"] = snapshot

    base = copy.deepcopy(result)
    base.pop("decision_consumption", None)
    result_sha = hashlib.sha256(canonical_json(base).encode("utf-8")).hexdigest()
    key = f"github-decision:{COMMENT_NODE}"
    local = {
        "authority_key": key,
        "payload_sha256": snapshot_sha,
        "action_kind": "CONTRACT_ACCEPT",
        "run_id": "gp001-product-authority-e2e-003",
        "state": "FINAL",
        "result_sha256": result_sha,
    }
    global_receipt = {
        **local,
        "not_after": DECISION_EXPIRES,
        "provider_created_at": PROVIDER_CREATED_AT,
        "provider_state": "GLOBAL_RESULT_BOUND",
    }
    result["decision_consumption"] = {**local, "global": global_receipt}
    return result


def _frozen(
    *,
    formation_transport: bool = True,
    transport_authority: bool = False,
    snapshot_transport_mismatch: bool = False,
    decision_app_mediated: bool = False,
) -> dict:
    request_payload = {
        "schema_version": "executor-github-request/1.0",
        "request_id": "gp001-product-authority-e2e-003",
        "target": {
            "repository": TARGET_REPO,
            "commit": TARGET_COMMIT,
            "tree": TARGET_TREE,
        },
        "task": {},
        "expires_at": REQUEST_EXPIRES,
        "nonce": "formation-test",
    }
    request_body = canonical_json(request_payload)
    request_actor = (
        {"login": "github-actions[bot]", "id": 41898282}
        if formation_transport
        else {"login": HUMAN_LOGIN, "id": HUMAN_ID}
    )
    request_evidence = {
        "provider": "GITHUB",
        "profile_id": "github-product-gp001",
        "repository": REPO,
        "issue_number": ISSUE,
        "issue_id": ISSUE_ID,
        "issue_node_id": ISSUE_NODE,
        "actor": request_actor,
        "body_sha256": _sha(request_body),
        "created_at": "2026-08-26T22:40:49Z",
        "observed_at": VERIFIED_AT,
        "evidence_ref": f"github:issue:{ISSUE_NODE}:{_sha(request_body)}",
    }
    decision_payload = {
        "schema_version": "executor-github-decision/1.0",
        "request": {
            "repository": REPO,
            "issue_number": ISSUE,
            "issue_node_id": ISSUE_NODE,
            "body_sha256": request_evidence["body_sha256"],
        },
        "draft_sha256": DRAFT_SHA,
        "decision": "ACCEPT",
        "valid_for_seconds": 3600,
        "nonce": "human-gp001-product-accept-005",
    }
    decision_body = canonical_json(decision_payload)
    decision_evidence = {
        "provider": "GITHUB",
        "profile_id": "github-product-gp001",
        "repository": REPO,
        "issue_number": ISSUE,
        "comment_id": COMMENT_ID,
        "comment_node_id": COMMENT_NODE,
        "actor": {"login": HUMAN_LOGIN, "id": HUMAN_ID},
        "body_sha256": _sha(decision_body),
        "decision": "ACCEPT",
        "draft_sha256": DRAFT_SHA,
        "created_at": DECISION_CREATED,
        "expires_at": DECISION_EXPIRES,
        "observed_at": VERIFIED_AT,
        "evidence_ref": f"github:comment:{COMMENT_NODE}:{_sha(decision_body)}",
    }
    request_event = {
        "url": f"https://api.github.com/repos/{REPO}/issues/{ISSUE}",
        "repository_url": f"https://api.github.com/repos/{REPO}",
        "number": ISSUE,
        "id": ISSUE_ID,
        "node_id": ISSUE_NODE,
        "state": "open",
        "body": request_body,
        "created_at": "2026-08-26T22:40:49Z",
        "updated_at": "2026-08-26T22:40:49Z",
        "author_association": "NONE" if formation_transport else "OWNER",
        "performed_via_github_app_present": True,
        "performed_via_github_app": (
            {"slug": "github-actions"} if formation_transport else None
        ),
        "user": {
            "login": request_actor["login"],
            "id": request_actor["id"],
            "type": "Bot" if formation_transport else "User",
        },
    }
    decision_event = {
        "url": f"https://api.github.com/repos/{REPO}/issues/comments/{COMMENT_ID}",
        "issue_url": f"https://api.github.com/repos/{REPO}/issues/{ISSUE}",
        "id": COMMENT_ID,
        "node_id": COMMENT_NODE,
        "body": decision_body,
        "created_at": DECISION_CREATED,
        "updated_at": DECISION_CREATED,
        "author_association": "OWNER",
        "performed_via_github_app_present": True,
        "performed_via_github_app": {"slug": "bad-app"} if decision_app_mediated else None,
        "user": {"login": HUMAN_LOGIN, "id": HUMAN_ID, "type": "User"},
    }
    snapshot = {
        "schema_version": AUTHORITY_SNAPSHOT_SCHEMA,
        "revocation_cutoff": REVOCATION_CUTOFF,
        "verified_at": VERIFIED_AT,
        "draft_sha256": DRAFT_SHA,
        "request": {
            "verified_evidence": request_evidence,
            "provider_event": request_event,
            "payload": request_payload,
            "target_commit": {
                "url": f"https://api.github.com/repos/{TARGET_REPO}/git/commits/{TARGET_COMMIT}",
                "sha": TARGET_COMMIT,
                "tree_sha": TARGET_TREE,
            },
        },
        "decision": {
            "verified_evidence": decision_evidence,
            "provider_event": decision_event,
            "payload": decision_payload,
        },
    }

    transport = None
    if formation_transport:
        transport = {
            "origin": "FORMATION_PUBLISHED_REQUEST",
            "authority": transport_authority,
            "publisher": "EXECUTOR_FORMATION",
            "provider": "GITHUB",
            "action_kind": "CREATE_ISSUE",
            "target": REPO,
            "object_id": str(ISSUE),
            "object_url": f"https://github.com/{REPO}/issues/{ISSUE}",
            "effect_sha256": "e" * 64,
            "observation_ref": "github:issue:transport-observation",
            "human_decision_required": True,
        }
        snapshot["request_transport_provenance"] = copy.deepcopy(transport)
        if snapshot_transport_mismatch:
            snapshot["request_transport_provenance"]["object_id"] = "999"

    contract = {
        "schema_version": (
            "executor-frozen-pilot-contract/1.2"
            if formation_transport
            else "executor-frozen-pilot-contract/1.0"
        ),
        "request_id": "gp001-product-authority-e2e-003",
        "target": request_payload["target"],
        "request_evidence": request_evidence,
        "decision_evidence": decision_evidence,
        "authority_snapshot": snapshot,
        "authority_snapshot_sha256": "",
        "draft_sha256": DRAFT_SHA,
        "status": "AUTHORIZED_AND_FROZEN",
        "executable": True,
    }
    result = {
        "schema_version": (
            "executor-pilot-decision-result/1.2"
            if formation_transport
            else "executor-pilot-decision-result/1.0"
        ),
        "status": "AUTHORIZED_AND_FROZEN",
        "contract": contract,
        "contract_sha256": "c" * 64,
        "draft_sha256": DRAFT_SHA,
        "authority_snapshot_sha256": "",
        "decision_evidence": decision_evidence,
        "executable": True,
    }
    if formation_transport:
        contract["authority_source"] = "VERIFIED_HUMAN_DECISION_ONLY"
        contract["authority_boundary"] = {
            "request_transport_is_authority": False,
            "human_decision_is_authority": True,
        }
        contract["request_transport_provenance"] = copy.deepcopy(transport)
        result["authority_source"] = "VERIFIED_HUMAN_DECISION_ONLY"
        result["request_transport_provenance"] = copy.deepcopy(transport)
    return _finalize_receipts(result)


class FrozenProductTransportAuthorityTests(unittest.TestCase):
    def test_formation_transport_bot_is_not_required_to_be_direct_human(self) -> None:
        request, decision = validate_frozen_pilot_authority(_frozen())
        self.assertTrue(request.evidence_ref.startswith("github:issue:"))
        self.assertEqual(decision.actor_login, HUMAN_LOGIN)
        self.assertEqual(decision.decision, "ACCEPT")

    def test_formation_transport_cannot_gain_authority(self) -> None:
        with self.assertRaisesRegex(FrozenPilotAuthorityError, "transport.*authority"):
            validate_frozen_pilot_authority(_frozen(transport_authority=True))

    def test_snapshot_transport_must_match_contract_transport(self) -> None:
        with self.assertRaisesRegex(FrozenPilotAuthorityError, "transport.*mismatch"):
            validate_frozen_pilot_authority(_frozen(snapshot_transport_mismatch=True))

    def test_human_decision_must_remain_direct_human(self) -> None:
        with self.assertRaisesRegex(FrozenPilotAuthorityError, "decision direct-human"):
            validate_frozen_pilot_authority(_frozen(decision_app_mediated=True))

    def test_legacy_contract_still_requires_direct_human_request(self) -> None:
        legacy = _frozen(formation_transport=False)
        event = legacy["contract"]["authority_snapshot"]["request"]["provider_event"]
        event["user"]["type"] = "Bot"
        snapshot = legacy["contract"]["authority_snapshot"]
        snapshot_sha = authority_snapshot_sha256(snapshot)
        legacy["contract"]["authority_snapshot_sha256"] = snapshot_sha
        legacy["authority_snapshot_sha256"] = snapshot_sha
        base = copy.deepcopy(legacy)
        base.pop("decision_consumption")
        result_sha = hashlib.sha256(canonical_json(base).encode("utf-8")).hexdigest()
        legacy["decision_consumption"]["payload_sha256"] = snapshot_sha
        legacy["decision_consumption"]["result_sha256"] = result_sha
        legacy["decision_consumption"]["global"]["payload_sha256"] = snapshot_sha
        legacy["decision_consumption"]["global"]["result_sha256"] = result_sha
        with self.assertRaisesRegex(FrozenPilotAuthorityError, "request direct-human"):
            validate_frozen_pilot_authority(legacy)


if __name__ == "__main__":
    unittest.main()
