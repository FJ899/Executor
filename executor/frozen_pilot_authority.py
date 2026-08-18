from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from executor.github_trust import GitHubEvidenceSource, GitHubTrustError, canonical_json
from executor.strict_json import StrictJsonError, loads_json_object


class FrozenPilotAuthorityError(ValueError):
    pass


AUTHORITY_SNAPSHOT_SCHEMA = "executor-github-contract-authority-snapshot/1.0"
REVOCATION_CUTOFF = (
    "FINAL_LIVE_VERIFICATION_CONDITIONAL_ON_SUCCESSFUL_GLOBAL_CONTRACT_ACCEPT"
)


class RecordingGitHubSource:
    """Record the exact provider objects consumed by authoritative GitHub verifiers."""

    def __init__(self, source: GitHubEvidenceSource):
        self.source = source
        self.records: dict[str, dict[str, Any]] = {}

    def fetch_json(self, url: str) -> dict[str, Any]:
        value = self.source.fetch_json(url)
        if not isinstance(value, dict):
            raise GitHubTrustError("GitHub provider response must be an object")
        self.records[url] = copy.deepcopy(value)
        return copy.deepcopy(value)


def _request_provider_event(issue: dict[str, Any]) -> dict[str, Any]:
    actor = issue.get("user")
    return {
        "url": issue.get("url"),
        "repository_url": issue.get("repository_url"),
        "number": issue.get("number"),
        "id": issue.get("id"),
        "node_id": issue.get("node_id"),
        "state": issue.get("state"),
        "body": issue.get("body"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "author_association": issue.get("author_association"),
        "performed_via_github_app_present": "performed_via_github_app" in issue,
        "performed_via_github_app": issue.get("performed_via_github_app"),
        "user": {
            "login": actor.get("login") if isinstance(actor, dict) else None,
            "id": actor.get("id") if isinstance(actor, dict) else None,
            "type": actor.get("type") if isinstance(actor, dict) else None,
        },
    }


def _decision_provider_event(comment: dict[str, Any]) -> dict[str, Any]:
    actor = comment.get("user")
    return {
        "url": comment.get("url"),
        "issue_url": comment.get("issue_url"),
        "id": comment.get("id"),
        "node_id": comment.get("node_id"),
        "body": comment.get("body"),
        "created_at": comment.get("created_at"),
        "updated_at": comment.get("updated_at"),
        "author_association": comment.get("author_association"),
        "performed_via_github_app_present": "performed_via_github_app" in comment,
        "performed_via_github_app": comment.get("performed_via_github_app"),
        "user": {
            "login": actor.get("login") if isinstance(actor, dict) else None,
            "id": actor.get("id") if isinstance(actor, dict) else None,
            "type": actor.get("type") if isinstance(actor, dict) else None,
        },
    }


def build_authority_snapshot(
    *,
    recording: RecordingGitHubSource,
    request: Any,
    decision: Any,
    draft_sha256: str,
) -> dict[str, Any]:
    issue_url = (
        f"https://api.github.com/repos/{request.repository}/issues/"
        f"{request.issue_number}"
    )
    comment_url = (
        f"https://api.github.com/repos/{request.repository}/issues/comments/"
        f"{decision.comment_id}"
    )
    target = request.payload["target"]
    commit_url = (
        f"https://api.github.com/repos/{target['repository']}/git/commits/"
        f"{target['commit']}"
    )
    try:
        issue = recording.records[issue_url]
        comment = recording.records[comment_url]
        commit = recording.records[commit_url]
    except KeyError as exc:
        raise FrozenPilotAuthorityError(
            "final live verification did not record all required provider evidence"
        ) from exc
    tree = commit.get("tree")
    return {
        "schema_version": AUTHORITY_SNAPSHOT_SCHEMA,
        "revocation_cutoff": REVOCATION_CUTOFF,
        "verified_at": decision.observed_at,
        "draft_sha256": draft_sha256,
        "request": {
            "verified_evidence": request.to_dict(),
            "provider_event": _request_provider_event(issue),
            "payload": copy.deepcopy(request.payload),
            "target_commit": {
                "url": commit_url,
                "sha": commit.get("sha"),
                "tree_sha": tree.get("sha") if isinstance(tree, dict) else None,
            },
        },
        "decision": {
            "verified_evidence": decision.to_dict(),
            "provider_event": _decision_provider_event(comment),
            "payload": copy.deepcopy(decision.payload),
        },
    }


def authority_snapshot_sha256(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class FrozenGitHubRequestAuthority:
    body_sha256: str
    evidence_ref: str


@dataclass(frozen=True)
class FrozenGitHubDecisionAuthority:
    body_sha256: str
    evidence_ref: str
    actor_login: str
    decision: str
    expires_at: str


def _parse_snapshot_body(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, str) or not value:
        raise FrozenPilotAuthorityError(
            f"{label} body is missing from frozen authority snapshot"
        )
    try:
        return loads_json_object(value)
    except StrictJsonError as exc:
        raise FrozenPilotAuthorityError(
            f"{label} body is invalid in frozen authority snapshot"
        ) from exc


def _parse_utc(value: object, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise FrozenPilotAuthorityError(f"{label} is not a UTC Z timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise FrozenPilotAuthorityError(f"{label} is invalid") from exc
    return parsed.astimezone(timezone.utc)


def validate_frozen_pilot_authority(
    frozen_result: dict[str, Any],
) -> tuple[FrozenGitHubRequestAuthority, FrozenGitHubDecisionAuthority]:
    """Validate immutable CONTRACT_ACCEPT snapshot + successful receipt, with no live read."""

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
        raise FrozenPilotAuthorityError(
            "frozen request evidence differs from authority snapshot"
        )
    if decision_evidence != contract.get("decision_evidence"):
        raise FrozenPilotAuthorityError(
            "frozen decision evidence differs from authority snapshot"
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
        raise FrozenPilotAuthorityError("frozen direct-human actor evidence is missing")
    for label, event, actor, evidence in (
        ("request", request_event, request_actor, request_evidence),
        ("decision", decision_event, decision_actor, decision_evidence),
    ):
        expected_actor = evidence.get("actor")
        if (
            actor.get("type") != "User"
            or not isinstance(expected_actor, dict)
            or actor.get("login") != expected_actor.get("login")
            or actor.get("id") != expected_actor.get("id")
            or event.get("author_association") not in {"OWNER", "MEMBER", "COLLABORATOR"}
            or event.get("performed_via_github_app_present") is not True
            or event.get("performed_via_github_app") is not None
        ):
            raise FrozenPilotAuthorityError(
                f"frozen {label} direct-human provenance mismatch"
            )
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
    decision_expiry = _parse_utc(
        decision_evidence.get("expires_at"), label="decision expires_at"
    )
    verified_at = _parse_utc(
        snapshot.get("verified_at"), label="authority snapshot verified_at"
    )
    request_expiry = _parse_utc(
        request_payload.get("expires_at"), label="request expires_at"
    )
    if expected_expiry != decision_expiry:
        raise FrozenPilotAuthorityError("frozen decision expiry derivation mismatch")
    if verified_at >= decision_expiry or verified_at >= request_expiry:
        raise FrozenPilotAuthorityError(
            "frozen authority was not fresh at the revocation cutoff"
        )

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
            raise FrozenPilotAuthorityError(
                f"{label} CONTRACT_ACCEPT authority key mismatch"
            )
        if receipt.get("payload_sha256") != snapshot_sha256:
            raise FrozenPilotAuthorityError(
                f"{label} CONTRACT_ACCEPT snapshot binding mismatch"
            )
        if receipt.get("action_kind") != "CONTRACT_ACCEPT":
            raise FrozenPilotAuthorityError(f"{label} receipt is not CONTRACT_ACCEPT")
        if receipt.get("run_id") != expected_run:
            raise FrozenPilotAuthorityError(
                f"{label} CONTRACT_ACCEPT run binding mismatch"
            )
        if receipt.get("state") != "FINAL":
            raise FrozenPilotAuthorityError(f"{label} CONTRACT_ACCEPT is not FINAL")
    if global_receipt.get("not_after") != decision_evidence.get("expires_at"):
        raise FrozenPilotAuthorityError("global CONTRACT_ACCEPT expiry binding mismatch")
    provider_created_at = _parse_utc(
        global_receipt.get("provider_created_at"),
        label="CONTRACT_ACCEPT provider_created_at",
    )
    not_after = _parse_utc(
        global_receipt.get("not_after"), label="CONTRACT_ACCEPT not_after"
    )
    if provider_created_at >= not_after:
        raise FrozenPilotAuthorityError("CONTRACT_ACCEPT provider time is not before expiry")

    base_result = copy.deepcopy(frozen_result)
    base_result.pop("decision_consumption", None)
    expected_result_sha = hashlib.sha256(
        canonical_json(base_result).encode("utf-8")
    ).hexdigest()
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
