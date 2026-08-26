from __future__ import annotations

import copy
import hashlib
from datetime import timedelta
from typing import Any

from executor.frozen_pilot_authority import (
    AUTHORITY_SNAPSHOT_SCHEMA,
    REVOCATION_CUTOFF,
    FrozenGitHubDecisionAuthority,
    FrozenGitHubRequestAuthority,
    FrozenPilotAuthorityError,
    _parse_snapshot_body,
    _parse_utc,
    authority_snapshot_sha256,
)
from executor.github_trust import canonical_json


def _validate_transport_provenance(
    *,
    frozen_result: dict[str, Any],
    contract: dict[str, Any],
    snapshot: dict[str, Any],
    request_evidence: dict[str, Any],
) -> dict[str, Any]:
    transport = contract.get("request_transport_provenance")
    if not isinstance(transport, dict):
        raise FrozenPilotAuthorityError("product frozen request transport provenance is missing")
    if frozen_result.get("request_transport_provenance") != transport:
        raise FrozenPilotAuthorityError("frozen result request transport provenance mismatch")
    if snapshot.get("request_transport_provenance") != transport:
        raise FrozenPilotAuthorityError("authority snapshot request transport provenance mismatch")
    if (
        transport.get("origin") != "FORMATION_PUBLISHED_REQUEST"
        or transport.get("authority") is not False
        or transport.get("publisher") != "EXECUTOR_FORMATION"
        or transport.get("provider") != "GITHUB"
        or transport.get("action_kind") != "CREATE_ISSUE"
        or transport.get("target") != request_evidence.get("repository")
        or transport.get("human_decision_required") is not True
    ):
        raise FrozenPilotAuthorityError("frozen product request transport semantics are invalid")
    if transport.get("object_id") != str(request_evidence.get("issue_number")):
        raise FrozenPilotAuthorityError("frozen request transport issue identity mismatch")
    expected_url = (
        f"https://github.com/{request_evidence.get('repository')}/issues/"
        f"{request_evidence.get('issue_number')}"
    )
    if transport.get("object_url") != expected_url:
        raise FrozenPilotAuthorityError("frozen request transport issue URL mismatch")
    for field in ("effect_sha256", "observation_ref"):
        if not isinstance(transport.get(field), str) or not transport[field]:
            raise FrozenPilotAuthorityError(f"frozen request transport {field} is missing")
    return transport


def validate_product_frozen_pilot_authority(
    frozen_result: dict[str, Any],
) -> tuple[FrozenGitHubRequestAuthority, FrozenGitHubDecisionAuthority]:
    """Validate a frozen product contract where Issue transport has zero Human authority.

    The request Issue is required to be the exact Formation-published provider object.
    Only the decision comment must carry provider-verifiable direct-human provenance.
    """

    if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN" or not frozen_result.get(
        "executable"
    ):
        raise FrozenPilotAuthorityError(
            "pilot execution requires AUTHORIZED_AND_FROZEN authority"
        )
    contract = frozen_result.get("contract")
    if not isinstance(contract, dict) or contract.get("status") != "AUTHORIZED_AND_FROZEN":
        raise FrozenPilotAuthorityError("frozen pilot contract is missing")
    if not contract.get("executable"):
        raise FrozenPilotAuthorityError("frozen pilot contract is not executable")
    if contract.get("authority_source") != "VERIFIED_HUMAN_DECISION_ONLY":
        raise FrozenPilotAuthorityError("product frozen authority source is invalid")

    snapshot = contract.get("authority_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != AUTHORITY_SNAPSHOT_SCHEMA:
        raise FrozenPilotAuthorityError("frozen authority snapshot is missing or unsupported")
    if snapshot.get("revocation_cutoff") != REVOCATION_CUTOFF:
        raise FrozenPilotAuthorityError("frozen authority snapshot has the wrong revocation cutoff")
    snapshot_sha256 = authority_snapshot_sha256(snapshot)
    if contract.get("authority_snapshot_sha256") != snapshot_sha256:
        raise FrozenPilotAuthorityError("frozen authority snapshot hash mismatch")
    if frozen_result.get("authority_snapshot_sha256") != snapshot_sha256:
        raise FrozenPilotAuthorityError("frozen result snapshot hash mismatch")
    if snapshot.get("draft_sha256") != contract.get("draft_sha256"):
        raise FrozenPilotAuthorityError("frozen authority snapshot draft binding mismatch")

    request_snapshot = snapshot.get("request")
    decision_snapshot = snapshot.get("decision")
    if not isinstance(request_snapshot, dict) or not isinstance(decision_snapshot, dict):
        raise FrozenPilotAuthorityError("frozen authority snapshot request/decision is missing")
    request_evidence = request_snapshot.get("verified_evidence")
    decision_evidence = decision_snapshot.get("verified_evidence")
    request_event = request_snapshot.get("provider_event")
    decision_event = decision_snapshot.get("provider_event")
    request_payload = request_snapshot.get("payload")
    decision_payload = decision_snapshot.get("payload")
    target_commit = request_snapshot.get("target_commit")
    for label, value in (
        ("request evidence", request_evidence),
        ("decision evidence", decision_evidence),
        ("request provider event", request_event),
        ("decision provider event", decision_event),
        ("request payload", request_payload),
        ("decision payload", decision_payload),
        ("target commit", target_commit),
    ):
        if not isinstance(value, dict):
            raise FrozenPilotAuthorityError(f"frozen authority {label} is missing")

    if request_evidence != contract.get("request_evidence"):
        raise FrozenPilotAuthorityError("frozen request evidence differs from authority snapshot")
    if decision_evidence != contract.get("decision_evidence"):
        raise FrozenPilotAuthorityError("frozen decision evidence differs from authority snapshot")

    transport = _validate_transport_provenance(
        frozen_result=frozen_result,
        contract=contract,
        snapshot=snapshot,
        request_evidence=request_evidence,
    )

    expected_issue_url = (
        f"https://api.github.com/repos/{request_evidence.get('repository')}/issues/"
        f"{request_evidence.get('issue_number')}"
    )
    if (
        request_event.get("url") != expected_issue_url
        or request_event.get("repository_url")
        != f"https://api.github.com/repos/{request_evidence.get('repository')}"
        or request_event.get("number") != request_evidence.get("issue_number")
        or request_event.get("id") != request_evidence.get("issue_id")
        or request_event.get("node_id") != request_evidence.get("issue_node_id")
    ):
        raise FrozenPilotAuthorityError("frozen request provider identity mismatch")

    expected_comment_url = (
        f"https://api.github.com/repos/{request_evidence.get('repository')}/issues/comments/"
        f"{decision_evidence.get('comment_id')}"
    )
    if (
        decision_event.get("url") != expected_comment_url
        or decision_event.get("issue_url") != expected_issue_url
        or decision_event.get("id") != decision_evidence.get("comment_id")
        or decision_event.get("node_id") != decision_evidence.get("comment_node_id")
    ):
        raise FrozenPilotAuthorityError("frozen decision provider identity mismatch")

    request_body = request_event.get("body")
    decision_body = decision_event.get("body")
    if not isinstance(request_body, str) or hashlib.sha256(
        request_body.encode("utf-8")
    ).hexdigest() != request_evidence.get("body_sha256"):
        raise FrozenPilotAuthorityError("frozen request body hash mismatch")
    if not isinstance(decision_body, str) or hashlib.sha256(
        decision_body.encode("utf-8")
    ).hexdigest() != decision_evidence.get("body_sha256"):
        raise FrozenPilotAuthorityError("frozen decision body hash mismatch")
    if _parse_snapshot_body(request_body, label="request") != request_payload:
        raise FrozenPilotAuthorityError("frozen request body/payload mismatch")
    if _parse_snapshot_body(decision_body, label="decision") != decision_payload:
        raise FrozenPilotAuthorityError("frozen decision body/payload mismatch")

    request_actor = request_event.get("user")
    decision_actor = decision_event.get("user")
    if not isinstance(request_actor, dict) or not isinstance(decision_actor, dict):
        raise FrozenPilotAuthorityError("frozen provider actor evidence is missing")
    expected_request_actor = request_evidence.get("actor")
    if (
        not isinstance(expected_request_actor, dict)
        or request_actor.get("login") != expected_request_actor.get("login")
        or request_actor.get("id") != expected_request_actor.get("id")
        or not isinstance(request_actor.get("type"), str)
        or not request_actor.get("type")
    ):
        raise FrozenPilotAuthorityError("frozen system request transport actor mismatch")

    expected_decision_actor = decision_evidence.get("actor")
    if (
        decision_actor.get("type") != "User"
        or not isinstance(expected_decision_actor, dict)
        or decision_actor.get("login") != expected_decision_actor.get("login")
        or decision_actor.get("id") != expected_decision_actor.get("id")
        or decision_event.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}
        or decision_event.get("performed_via_github_app_present") is not True
        or decision_event.get("performed_via_github_app") is not None
    ):
        raise FrozenPilotAuthorityError("frozen decision direct-human provenance mismatch")

    if request_event.get("state") != "open":
        raise FrozenPilotAuthorityError("request was not open at the revocation cutoff")
    if decision_event.get("created_at") != decision_event.get("updated_at"):
        raise FrozenPilotAuthorityError("decision was edited at the revocation cutoff")

    request_binding = decision_payload.get("request")
    expected_request_binding = {
        "repository": request_evidence.get("repository"),
        "issue_number": request_evidence.get("issue_number"),
        "issue_node_id": request_evidence.get("issue_node_id"),
        "body_sha256": request_evidence.get("body_sha256"),
    }
    if request_binding != expected_request_binding:
        raise FrozenPilotAuthorityError("frozen decision request binding mismatch")
    if decision_payload.get("draft_sha256") != contract.get("draft_sha256"):
        raise FrozenPilotAuthorityError("frozen decision draft binding mismatch")
    if decision_payload.get("decision") != "ACCEPT" or decision_evidence.get("decision") != "ACCEPT":
        raise FrozenPilotAuthorityError("frozen authority is not an ACCEPT")
    if decision_evidence.get("draft_sha256") != contract.get("draft_sha256"):
        raise FrozenPilotAuthorityError("frozen decision evidence draft mismatch")

    valid_for_seconds = decision_payload.get("valid_for_seconds")
    if type(valid_for_seconds) is not int or valid_for_seconds <= 0:
        raise FrozenPilotAuthorityError("frozen decision lifetime is invalid")
    created_at = _parse_utc(decision_event.get("created_at"), label="decision created_at")
    expected_expiry = created_at + timedelta(seconds=valid_for_seconds)
    decision_expiry = _parse_utc(decision_evidence.get("expires_at"), label="decision expires_at")
    verified_at = _parse_utc(snapshot.get("verified_at"), label="authority snapshot verified_at")
    request_expiry = _parse_utc(request_payload.get("expires_at"), label="request expires_at")
    if expected_expiry != decision_expiry:
        raise FrozenPilotAuthorityError("frozen decision expiry derivation mismatch")
    if verified_at >= decision_expiry or verified_at >= request_expiry:
        raise FrozenPilotAuthorityError("frozen authority was not fresh at the revocation cutoff")

    target = contract.get("target")
    if not isinstance(target, dict) or (
        target_commit.get("sha") != target.get("commit")
        or target_commit.get("tree_sha") != target.get("tree")
    ):
        raise FrozenPilotAuthorityError("frozen target commit/tree evidence mismatch")

    consumption = frozen_result.get("decision_consumption")
    if not isinstance(consumption, dict):
        raise FrozenPilotAuthorityError("successful CONTRACT_ACCEPT receipt is missing")
    global_receipt = consumption.get("global")
    if not isinstance(global_receipt, dict):
        raise FrozenPilotAuthorityError("global CONTRACT_ACCEPT receipt is missing")
    expected_key = f"github-decision:{decision_evidence.get('comment_node_id')}"
    expected_run = str(contract.get("request_id", ""))
    for label, receipt in (("local", consumption), ("global", global_receipt)):
        if receipt.get("authority_key") != expected_key:
            raise FrozenPilotAuthorityError(f"{label} CONTRACT_ACCEPT authority key mismatch")
        if receipt.get("payload_sha256") != snapshot_sha256:
            raise FrozenPilotAuthorityError(f"{label} CONTRACT_ACCEPT snapshot binding mismatch")
        if receipt.get("action_kind") != "CONTRACT_ACCEPT":
            raise FrozenPilotAuthorityError(f"{label} receipt is not CONTRACT_ACCEPT")
        if receipt.get("run_id") != expected_run:
            raise FrozenPilotAuthorityError(f"{label} CONTRACT_ACCEPT run binding mismatch")
        if receipt.get("state") != "FINAL":
            raise FrozenPilotAuthorityError(f"{label} CONTRACT_ACCEPT is not FINAL")
    if global_receipt.get("not_after") != decision_evidence.get("expires_at"):
        raise FrozenPilotAuthorityError("global CONTRACT_ACCEPT expiry binding mismatch")
    provider_created_at = _parse_utc(
        global_receipt.get("provider_created_at"), label="CONTRACT_ACCEPT provider_created_at"
    )
    not_after = _parse_utc(global_receipt.get("not_after"), label="CONTRACT_ACCEPT not_after")
    if provider_created_at >= not_after:
        raise FrozenPilotAuthorityError("CONTRACT_ACCEPT provider time is not before expiry")

    base_result = copy.deepcopy(frozen_result)
    base_result.pop("decision_consumption", None)
    expected_result_sha = hashlib.sha256(canonical_json(base_result).encode("utf-8")).hexdigest()
    if (
        consumption.get("result_sha256") != expected_result_sha
        or global_receipt.get("result_sha256") != expected_result_sha
    ):
        raise FrozenPilotAuthorityError("CONTRACT_ACCEPT result binding mismatch")

    actor = decision_evidence.get("actor")
    if not isinstance(actor, dict) or not isinstance(actor.get("login"), str):
        raise FrozenPilotAuthorityError("frozen decision actor is missing")
    for field in ("body_sha256", "evidence_ref"):
        if not isinstance(request_evidence.get(field), str):
            raise FrozenPilotAuthorityError(f"frozen request {field} is missing")
    for field in ("body_sha256", "evidence_ref", "expires_at"):
        if not isinstance(decision_evidence.get(field), str):
            raise FrozenPilotAuthorityError(f"frozen decision {field} is missing")

    # Prevent a frozen contract from silently dropping its zero-authority transport proof.
    if transport.get("object_id") != str(request_evidence["issue_number"]):
        raise FrozenPilotAuthorityError("frozen request transport/evidence binding mismatch")

    return (
        FrozenGitHubRequestAuthority(
            body_sha256=request_evidence["body_sha256"],
            evidence_ref=request_evidence["evidence_ref"],
        ),
        FrozenGitHubDecisionAuthority(
            body_sha256=decision_evidence["body_sha256"],
            evidence_ref=decision_evidence["evidence_ref"],
            actor_login=actor["login"],
            decision="ACCEPT",
            expires_at=decision_evidence["expires_at"],
        ),
    )
