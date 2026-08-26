from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timezone
from typing import Any

from executor.frozen_pilot_authority import (
    REVOCATION_CUTOFF,
    RecordingGitHubSource,
    authority_snapshot_sha256,
    build_authority_snapshot,
)
from executor.github_authority import GovernedAuthorityLedger
from executor.github_trust import (
    GitHubEvidenceSource,
    GitHubTrustError,
    GitHubTrustProfile,
    VerifiedGitHubDecision,
    VerifiedGitHubRequest,
    canonical_json,
    verify_github_decision,
    verify_github_request,
)


class PilotContractError(ValueError):
    pass


_FORMATION_REQUEST_SCHEMA = "executor-canonical-contract-request/1.0"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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
            "global_consumption": "GITHUB_REF_REQUIRED",
        },
        "solution_boundary": {
            "owner": "EXTERNAL_INTELLIGENCE",
            "effect_authority": False,
        },
        "status": "AWAITING_VERIFIED_GITHUB_DECISION",
        "executable": False,
    }


def _validated_formation_binding(
    formation_request: dict[str, Any],
    *,
    request: VerifiedGitHubRequest,
) -> dict[str, Any]:
    if (
        not isinstance(formation_request, dict)
        or formation_request.get("schema_version") != _FORMATION_REQUEST_SCHEMA
        or formation_request.get("status") != "AWAITING_VERIFIED_HUMAN_AUTHORIZATION"
        or formation_request.get("executable") is not False
    ):
        raise PilotContractError("canonical formation request is missing or invalid")
    payload = formation_request.get("github_request_payload")
    if not isinstance(payload, dict) or payload != request.payload:
        raise PilotContractError(
            "verified GitHub request differs from the exact formation-produced request"
        )
    binding = formation_request.get("formation_binding")
    required = {
        "executor_repository",
        "executor_commit",
        "formation_profile",
        "formation_profile_sha256",
        "canonical_task_sha256",
        "draft_sha256",
    }
    if not isinstance(binding, dict) or set(binding) != required:
        raise PilotContractError("formation binding is incomplete")
    if binding.get("executor_repository") != "FJ899/Executor":
        raise PilotContractError("formation binding repository is unsupported")
    for field in ("formation_profile_sha256", "canonical_task_sha256", "draft_sha256"):
        value = binding.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(ch not in "0123456789abcdef" for ch in value)
        ):
            raise PilotContractError(f"formation binding {field} is invalid")
    return copy.deepcopy(binding)


def build_pilot_draft_from_formation(
    formation_request: dict[str, Any],
    request: VerifiedGitHubRequest,
) -> dict[str, Any]:
    draft = build_pilot_draft(request)
    draft["formation_binding"] = _validated_formation_binding(
        formation_request,
        request=request,
    )
    draft["schema_version"] = "executor-pilot-draft/1.1"
    return draft


def apply_github_decision(
    *,
    draft: dict[str, Any],
    decision: VerifiedGitHubDecision,
    source: GitHubEvidenceSource,
    profile: GitHubTrustProfile,
    ledger: GovernedAuthorityLedger,
    formation_request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Final-live verify and consume one exact GitHub contract decision.

    When ``formation_request`` is supplied, the provider request must be the
    byte-semantically identical request produced by RequestToContract001. This
    is the canonical product path. The legacy GitHub-only path remains readable
    for historical/recovery compatibility but does not manufacture a formation
    binding.
    """

    current = _utc_now().astimezone(timezone.utc)
    recording = RecordingGitHubSource(source)
    final_request = verify_github_request(
        recording,
        profile=profile,
        issue_number=decision.issue_number,
        now=current,
    )
    final_draft = (
        build_pilot_draft_from_formation(formation_request, final_request)
        if formation_request is not None
        else build_pilot_draft(final_request)
    )
    expected_draft = pilot_draft_sha256(final_draft)
    if expected_draft != pilot_draft_sha256(draft):
        raise PilotContractError("GitHub request changed before final live verification")
    final_decision = verify_github_decision(
        recording,
        profile=profile,
        request=final_request,
        comment_id=decision.comment_id,
        draft_sha256=expected_draft,
        now=current,
    )
    if (
        final_decision.comment_id != decision.comment_id
        or final_decision.comment_node_id != decision.comment_node_id
    ):
        raise PilotContractError(
            "final GitHub decision identity differs from reviewed decision"
        )

    snapshot = build_authority_snapshot(
        recording=recording,
        request=final_request,
        decision=final_decision,
        draft_sha256=expected_draft,
    )
    snapshot_sha256 = authority_snapshot_sha256(snapshot)
    consumption = ledger.consume(
        authority_key=f"github-decision:{final_decision.comment_node_id}",
        payload_sha256=snapshot_sha256,
        action_kind=f"CONTRACT_{final_decision.decision}",
        run_id=str(final_draft.get("request_id", "")),
        not_after=final_decision.expires_at,
    )

    formation_binding = copy.deepcopy(final_draft.get("formation_binding"))
    common = {
        "schema_version": "executor-pilot-decision-result/1.1",
        "draft_sha256": expected_draft,
        "formation_binding": formation_binding,
        "authority_snapshot": snapshot,
        "authority_snapshot_sha256": snapshot_sha256,
        "decision_evidence": final_decision.to_dict(),
        "executable": False,
    }

    if final_decision.decision == "MODIFY":
        result = {
            **common,
            "status": "MODIFICATION_REQUIRED",
            "next_formation_status": "REQUEST_RECEIVED_AFTER_REVISION",
            "requires_new_draft": True,
            "requires_new_validation": True,
            "requires_new_human_decision": True,
        }
    elif final_decision.decision == "REJECT":
        result = {
            **common,
            "status": "REJECTED",
            "terminal": True,
            "execution_permitted": False,
        }
    elif final_decision.decision == "ACCEPT":
        contract = {
            "schema_version": "executor-frozen-pilot-contract/1.1",
            "request_id": final_draft["request_id"],
            "target": copy.deepcopy(final_draft["target"]),
            "task": copy.deepcopy(final_draft["task"]),
            "formation_binding": formation_binding,
            "request_evidence": final_request.to_dict(),
            "decision_evidence": final_decision.to_dict(),
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "draft_sha256": expected_draft,
            "authority_boundary": {
                **copy.deepcopy(final_draft["authority_boundary"]),
                "revocation_cutoff": REVOCATION_CUTOFF,
            },
            "solution_boundary": copy.deepcopy(final_draft["solution_boundary"]),
            "status": "AUTHORIZED_AND_FROZEN",
            "executable": True,
        }
        contract_sha256 = hashlib.sha256(
            canonical_json(contract).encode("utf-8")
        ).hexdigest()
        result = {
            "schema_version": "executor-pilot-decision-result/1.1",
            "status": "AUTHORIZED_AND_FROZEN",
            "contract": contract,
            "contract_sha256": contract_sha256,
            "draft_sha256": expected_draft,
            "formation_binding": formation_binding,
            "authority_snapshot_sha256": snapshot_sha256,
            "decision_evidence": final_decision.to_dict(),
            "executable": True,
        }
    else:
        raise GitHubTrustError("unsupported verified GitHub decision")

    result["decision_consumption"] = ledger.bind_result(
        consumption=consumption,
        result=result,
    )
    return result
