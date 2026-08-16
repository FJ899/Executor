from __future__ import annotations

import copy
import hashlib
from typing import Any

from executor.authority_ledger import AtomicAuthorityLedger
from executor.github_trust import (
    GitHubTrustError,
    VerifiedGitHubDecision,
    VerifiedGitHubRequest,
    canonical_json,
)


class PilotContractError(ValueError):
    pass


def _draft_hash_material(draft: dict[str, Any]) -> dict[str, Any]:
    material = copy.deepcopy(draft)
    request_evidence = material.get("request_evidence")
    if not isinstance(request_evidence, dict):
        raise PilotContractError("draft request evidence is missing")
    request_evidence.pop("observed_at", None)
    return material


def pilot_draft_sha256(draft: dict[str, Any]) -> str:
    material = _draft_hash_material(draft)
    return hashlib.sha256(canonical_json(material).encode("utf-8")).hexdigest()


def build_pilot_draft(request: VerifiedGitHubRequest) -> dict[str, Any]:
    target = copy.deepcopy(request.payload["target"])
    task = copy.deepcopy(request.payload["task"])
    return {
        "schema_version": "executor-pilot-draft/1.0",
        "request_id": request.payload["request_id"],
        "request_evidence": request.to_dict(),
        "target": target,
        "task": task,
        "authority_boundary": {
            "provider": "GITHUB",
            "required_decisions": ["ACCEPT", "MODIFY", "REJECT"],
            "effect": "BOUNDED_DRAFT_PR_ONLY",
            "merge": False,
            "deploy": False,
            "release": False,
        },
        "solution_boundary": {
            "owner": "EXTERNAL_INTELLIGENCE",
            "effect_authority": False,
        },
        "status": "AWAITING_VERIFIED_GITHUB_DECISION",
        "executable": False,
    }


def apply_github_decision(
    *,
    draft: dict[str, Any],
    decision: VerifiedGitHubDecision,
    ledger: AtomicAuthorityLedger,
) -> dict[str, Any]:
    expected_draft = pilot_draft_sha256(draft)
    if decision.draft_sha256 != expected_draft:
        raise PilotContractError("verified decision does not match the current draft")
    request_evidence = draft.get("request_evidence")
    if not isinstance(request_evidence, dict):
        raise PilotContractError("draft request evidence is missing")
    if decision.repository != request_evidence.get("repository") or (
        decision.issue_number != request_evidence.get("issue_number")
    ):
        raise PilotContractError("decision belongs to a different request event")

    consumption = ledger.consume(
        authority_key=f"github-decision:{decision.comment_node_id}",
        payload_sha256=decision.body_sha256,
        action_kind=f"CONTRACT_{decision.decision}",
        run_id=str(draft.get("request_id", "")),
    )
    if decision.decision == "MODIFY":
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "MODIFICATION_REQUIRED",
            "draft_sha256": expected_draft,
            "decision_evidence": decision.to_dict(),
            "executable": False,
        }
    elif decision.decision == "REJECT":
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "REJECTED",
            "draft_sha256": expected_draft,
            "decision_evidence": decision.to_dict(),
            "executable": False,
        }
    elif decision.decision == "ACCEPT":
        contract = {
            "schema_version": "executor-frozen-pilot-contract/1.0",
            "request_id": draft["request_id"],
            "target": copy.deepcopy(draft["target"]),
            "task": copy.deepcopy(draft["task"]),
            "request_evidence": copy.deepcopy(draft["request_evidence"]),
            "decision_evidence": decision.to_dict(),
            "draft_sha256": expected_draft,
            "authority_boundary": copy.deepcopy(draft["authority_boundary"]),
            "solution_boundary": copy.deepcopy(draft["solution_boundary"]),
            "status": "AUTHORIZED_AND_FROZEN",
            "executable": True,
        }
        contract_sha256 = hashlib.sha256(
            canonical_json(contract).encode("utf-8")
        ).hexdigest()
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "AUTHORIZED_AND_FROZEN",
            "contract": contract,
            "contract_sha256": contract_sha256,
            "draft_sha256": expected_draft,
            "decision_evidence": decision.to_dict(),
            "executable": True,
        }
    else:
        raise GitHubTrustError("unsupported verified GitHub decision")
    bound = ledger.bind_result(
        execution_token=consumption.execution_token,
        result=result,
    )
    result["decision_consumption"] = bound.to_dict()
    return result
