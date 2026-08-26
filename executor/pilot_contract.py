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


def _require_sha256(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise PilotContractError(f"{label} must be a lowercase SHA-256")
    return value


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


def _validate_formation_binding(
    binding: dict[str, Any],
    *,
    authority_draft_sha256: str,
    request_payload: dict[str, Any],
    request_id: str,
) -> None:
    if binding.get("schema_version") != "executor-contract-formation-binding/1.0":
        raise PilotContractError("formation binding schema is missing or unsupported")

    draft = binding.get("draft")
    if not isinstance(draft, dict):
        raise PilotContractError("formation binding draft is missing")
    computed_draft_sha256 = hashlib.sha256(
        canonical_json(draft).encode("utf-8")
    ).hexdigest()
    if computed_draft_sha256 != authority_draft_sha256:
        raise PilotContractError("formation binding draft content hash mismatch")
    if binding.get("draft_sha256") != authority_draft_sha256:
        raise PilotContractError("formation binding draft hash mismatch")

    if binding.get("request_id") != request_id or draft.get("request_id") != request_id:
        raise PilotContractError("formation binding request id mismatch")
    if binding.get("authority_request_payload") != request_payload:
        raise PilotContractError("formation binding request payload mismatch")
    expected_request_sha256 = hashlib.sha256(
        canonical_json(request_payload).encode("utf-8")
    ).hexdigest()
    if binding.get("authority_request_payload_sha256") != expected_request_sha256:
        raise PilotContractError("formation binding request payload hash mismatch")

    expected_pairs = (
        ("executor_repository", "executor_repository"),
        ("executor_commit", "executor_commit"),
        ("formation_profile_sha256", "profile_sha256"),
        ("canonical_task_sha256", "canonical_task_sha256"),
        ("draft_version", "draft_version"),
        ("supersedes_draft_sha256", "supersedes_draft_sha256"),
    )
    for binding_key, draft_key in expected_pairs:
        if binding.get(binding_key) != draft.get(draft_key):
            raise PilotContractError(
                f"formation binding {binding_key} differs from hashed formation draft"
            )
    if binding.get("formation_profile") != draft.get("profile_id"):
        raise PilotContractError(
            "formation binding profile identity differs from hashed formation draft"
        )

    invalidated = binding.get("invalidated_draft_sha256s")
    if not isinstance(invalidated, list) or not all(
        isinstance(item, str) and len(item) == 64 for item in invalidated
    ):
        raise PilotContractError("formation invalidated draft set is malformed")
    supersedes = binding.get("supersedes_draft_sha256")
    if supersedes is not None and supersedes not in invalidated:
        raise PilotContractError(
            "formation superseded draft is not recorded as invalidated"
        )


def apply_github_decision(
    *,
    draft: dict[str, Any],
    decision: VerifiedGitHubDecision,
    source: GitHubEvidenceSource,
    profile: GitHubTrustProfile,
    ledger: GovernedAuthorityLedger,
    authority_draft_sha256: str | None = None,
    expected_request_payload: dict[str, Any] | None = None,
    formation_binding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Final-live verify and consume one exact GitHub contract decision.

    Existing P4 callers keep the canonical pilot draft as the authority-bearing
    identity. Contract formation may use a different governed draft hash only
    when the exact generated provider request and complete formation binding are
    supplied together and independently validated before authority consumption.
    """

    formation_values = (
        authority_draft_sha256,
        expected_request_payload,
        formation_binding,
    )
    formation_mode = any(value is not None for value in formation_values)
    if formation_mode and not all(value is not None for value in formation_values):
        raise PilotContractError(
            "formation authority override requires draft hash, request payload and binding"
        )

    current = _utc_now().astimezone(timezone.utc)
    recording = RecordingGitHubSource(source)
    final_request = verify_github_request(
        recording,
        profile=profile,
        issue_number=decision.issue_number,
        now=current,
    )

    final_draft = build_pilot_draft(final_request)
    pilot_draft_hash = pilot_draft_sha256(final_draft)
    if pilot_draft_hash != pilot_draft_sha256(draft):
        raise PilotContractError("GitHub request changed before final live verification")

    if formation_mode:
        if not isinstance(expected_request_payload, dict):
            raise PilotContractError("formation expected request payload must be an object")
        if final_request.payload != expected_request_payload:
            raise PilotContractError(
                "GitHub request payload differs from the governed formation export"
            )
        authority_hash = _require_sha256(
            authority_draft_sha256,
            label="authority_draft_sha256",
        )
        if not isinstance(formation_binding, dict):
            raise PilotContractError("formation binding must be an object")
        _validate_formation_binding(
            formation_binding,
            authority_draft_sha256=authority_hash,
            request_payload=final_request.payload,
            request_id=str(final_draft.get("request_id", "")),
        )
    else:
        authority_hash = pilot_draft_hash

    if decision.draft_sha256 != authority_hash:
        raise PilotContractError(
            "reviewed GitHub decision is bound to a different authority draft"
        )

    final_decision = verify_github_decision(
        recording,
        profile=profile,
        request=final_request,
        comment_id=decision.comment_id,
        draft_sha256=authority_hash,
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
        draft_sha256=authority_hash,
    )
    snapshot_sha256 = authority_snapshot_sha256(snapshot)
    consumption = ledger.consume(
        authority_key=f"github-decision:{final_decision.comment_node_id}",
        payload_sha256=snapshot_sha256,
        action_kind=f"CONTRACT_{final_decision.decision}",
        run_id=str(final_draft.get("request_id", "")),
        not_after=final_decision.expires_at,
    )

    if final_decision.decision == "MODIFY":
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "MODIFICATION_REQUIRED",
            "draft_sha256": authority_hash,
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "decision_evidence": final_decision.to_dict(),
            "executable": False,
        }
    elif final_decision.decision == "REJECT":
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "REJECTED",
            "draft_sha256": authority_hash,
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "decision_evidence": final_decision.to_dict(),
            "executable": False,
        }
    elif final_decision.decision == "ACCEPT":
        contract = {
            "schema_version": "executor-frozen-pilot-contract/1.0",
            "request_id": final_draft["request_id"],
            "target": copy.deepcopy(final_draft["target"]),
            "task": copy.deepcopy(final_draft["task"]),
            "request_evidence": final_request.to_dict(),
            "decision_evidence": final_decision.to_dict(),
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "draft_sha256": authority_hash,
            "authority_boundary": {
                **copy.deepcopy(final_draft["authority_boundary"]),
                "revocation_cutoff": REVOCATION_CUTOFF,
            },
            "solution_boundary": copy.deepcopy(final_draft["solution_boundary"]),
            "status": "AUTHORIZED_AND_FROZEN",
            "executable": True,
        }
        if formation_mode:
            contract["formation_binding"] = copy.deepcopy(formation_binding)
        contract_sha256 = hashlib.sha256(
            canonical_json(contract).encode("utf-8")
        ).hexdigest()
        result = {
            "schema_version": "executor-pilot-decision-result/1.0",
            "status": "AUTHORIZED_AND_FROZEN",
            "contract": contract,
            "contract_sha256": contract_sha256,
            "draft_sha256": authority_hash,
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
