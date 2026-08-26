from __future__ import annotations

import copy
import hashlib
from datetime import datetime, timedelta, timezone
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
    _SAFE_ID,
    _SHA256,
    _VERIFIED_EVIDENCE_PROOF,
    _exact_keys,
    _parse_utc,
    _validate_request_payload,
    _verify_actor,
    canonical_json,
    sha256_text,
)
from executor.pilot_contract import (
    PilotContractError,
    build_pilot_draft_from_formation,
    pilot_draft_sha256,
)
from executor.strict_json import StrictJsonError, loads_json_object


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _transport_actor(event: dict[str, Any]) -> tuple[str, int]:
    """Capture provider identity without granting the request transport human authority."""

    actor = event.get("user")
    if not isinstance(actor, dict):
        raise GitHubTrustError("formation-published request has no GitHub transport actor")
    login = actor.get("login")
    actor_id = actor.get("id")
    actor_type = actor.get("type")
    if (
        not isinstance(login, str)
        or not login
        or type(actor_id) is not int
        or not isinstance(actor_type, str)
        or not actor_type
    ):
        raise GitHubTrustError("formation-published request actor identity is incomplete")
    return login, actor_id


def verify_formation_published_request(
    source: GitHubEvidenceSource,
    *,
    profile: GitHubTrustProfile,
    issue_number: int,
    expected_payload: dict[str, Any],
    now: datetime | None = None,
) -> VerifiedGitHubRequest:
    """Verify a Formation-created GitHub Issue strictly as zero-authority transport.

    The Issue actor may be a bot, app, or service credential. Human authority is
    intentionally absent here and is established only by verify_product_github_decision.
    """

    if type(issue_number) is not int or issue_number <= 0:
        raise GitHubTrustError("issue_number must be a positive integer")
    if not isinstance(expected_payload, dict):
        raise GitHubTrustError("expected formation request payload must be an object")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    api_url = (
        f"https://api.github.com/repos/{profile.intake_repository}/issues/"
        f"{issue_number}"
    )
    issue = source.fetch_json(api_url)
    expected_repo_url = f"https://api.github.com/repos/{profile.intake_repository}"
    if (
        issue.get("url") != api_url
        or issue.get("repository_url") != expected_repo_url
        or issue.get("number") != issue_number
        or "pull_request" in issue
    ):
        raise GitHubTrustError("formation-published GitHub issue identity does not match")
    if issue.get("state") != "open":
        raise GitHubTrustError("formation-published request issue must remain open")

    login, actor_id = _transport_actor(issue)
    body = issue.get("body")
    if not isinstance(body, str) or not body:
        raise GitHubTrustError("formation-published request body is missing")
    try:
        payload = loads_json_object(body)
    except StrictJsonError as exc:
        raise GitHubTrustError(f"formation-published request body is invalid: {exc}") from exc
    _validate_request_payload(payload, profile=profile, now=current)
    if payload != expected_payload:
        raise GitHubTrustError(
            "formation-published GitHub payload differs from the exact canonical request"
        )

    target = payload["target"]
    commit_url = (
        f"https://api.github.com/repos/{target['repository']}/git/commits/"
        f"{target['commit']}"
    )
    commit = source.fetch_json(commit_url)
    commit_tree = commit.get("tree")
    if (
        commit.get("sha") != target["commit"]
        or not isinstance(commit_tree, dict)
        or commit_tree.get("sha") != target["tree"]
    ):
        raise GitHubTrustError(
            "formation-published request commit/tree binding does not match provider"
        )

    created_at = issue.get("created_at")
    created = _parse_utc(created_at, label="formation-published request created_at")
    if created > current + timedelta(minutes=5):
        raise GitHubTrustError("formation-published request event is from the future")
    issue_id = issue.get("id")
    node_id = issue.get("node_id")
    if type(issue_id) is not int or not isinstance(node_id, str) or not node_id:
        raise GitHubTrustError("formation-published request lacks immutable event identity")

    return VerifiedGitHubRequest(
        profile_id=profile.profile_id,
        repository=profile.intake_repository,
        issue_number=issue_number,
        issue_id=issue_id,
        issue_node_id=node_id,
        actor_login=login,
        actor_id=actor_id,
        body_sha256=sha256_text(body),
        created_at=created_at,
        observed_at=current.isoformat().replace("+00:00", "Z"),
        payload=payload,
        _proof=_VERIFIED_EVIDENCE_PROOF,
    )


def verify_product_github_decision(
    source: GitHubEvidenceSource,
    *,
    profile: GitHubTrustProfile,
    request: VerifiedGitHubRequest,
    comment_id: int,
    draft_sha256: str,
    now: datetime | None = None,
) -> VerifiedGitHubDecision:
    """Verify the sole Human authority event for the Formation product path."""

    if request.profile_id != profile.profile_id:
        raise GitHubTrustError("request was verified under a different trust profile")
    if type(comment_id) is not int or comment_id <= 0:
        raise GitHubTrustError("comment_id must be a positive integer")
    if _SHA256.fullmatch(draft_sha256) is None:
        raise GitHubTrustError("draft_sha256 is invalid")

    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    api_url = (
        f"https://api.github.com/repos/{profile.intake_repository}/issues/comments/"
        f"{comment_id}"
    )
    comment = source.fetch_json(api_url)
    issue_url = (
        f"https://api.github.com/repos/{profile.intake_repository}/issues/"
        f"{request.issue_number}"
    )
    if comment.get("url") != api_url or comment.get("issue_url") != issue_url:
        raise GitHubTrustError("GitHub decision is attached to the wrong request")

    login, actor_id = _verify_actor(comment, profile=profile, label="decision")
    body = comment.get("body")
    if not isinstance(body, str) or not body:
        raise GitHubTrustError("GitHub decision body is missing")
    try:
        payload = loads_json_object(body)
    except StrictJsonError as exc:
        raise GitHubTrustError(f"GitHub decision body is invalid: {exc}") from exc

    _exact_keys(
        payload,
        {
            "schema_version",
            "request",
            "draft_sha256",
            "decision",
            "valid_for_seconds",
            "nonce",
        },
        label="decision payload",
    )
    if payload.get("schema_version") != "executor-github-decision/1.0":
        raise GitHubTrustError("unsupported GitHub decision schema")
    if payload.get("decision") not in {"ACCEPT", "MODIFY", "REJECT"}:
        raise GitHubTrustError("GitHub decision must be ACCEPT, MODIFY or REJECT")
    if payload.get("draft_sha256") != draft_sha256:
        raise GitHubTrustError("GitHub decision is bound to a different draft")
    if not isinstance(payload.get("nonce"), str) or _SAFE_ID.fullmatch(payload["nonce"]) is None:
        raise GitHubTrustError("decision nonce is invalid")

    valid_for_seconds = payload.get("valid_for_seconds")
    if type(valid_for_seconds) is not int or not (
        60 <= valid_for_seconds <= profile.max_decision_lifetime_seconds
    ):
        raise GitHubTrustError("decision valid_for_seconds exceeds the trust profile")

    request_ref = payload.get("request")
    if not isinstance(request_ref, dict):
        raise GitHubTrustError("decision request binding must be an object")
    _exact_keys(
        request_ref,
        {"repository", "issue_number", "issue_node_id", "body_sha256"},
        label="decision request binding",
    )
    if request_ref != {
        "repository": request.repository,
        "issue_number": request.issue_number,
        "issue_node_id": request.issue_node_id,
        "body_sha256": request.body_sha256,
    }:
        raise GitHubTrustError("GitHub decision request binding is stale or mismatched")

    created_at = comment.get("created_at")
    updated_at = comment.get("updated_at")
    if created_at != updated_at:
        raise GitHubTrustError("edited GitHub decisions are not accepted")
    created = _parse_utc(created_at, label="decision created_at")
    expires = created + timedelta(seconds=valid_for_seconds)
    if created > current + timedelta(minutes=5) or expires <= current:
        raise GitHubTrustError("GitHub decision is not currently fresh")
    comment_node_id = comment.get("node_id")
    if type(comment.get("id")) is not int or not isinstance(comment_node_id, str):
        raise GitHubTrustError("GitHub decision lacks immutable event identity")

    return VerifiedGitHubDecision(
        profile_id=profile.profile_id,
        repository=request.repository,
        issue_number=request.issue_number,
        comment_id=comment["id"],
        comment_node_id=comment_node_id,
        actor_login=login,
        actor_id=actor_id,
        body_sha256=sha256_text(body),
        decision=payload["decision"],
        draft_sha256=draft_sha256,
        created_at=created_at,
        expires_at=expires.isoformat().replace("+00:00", "Z"),
        observed_at=current.isoformat().replace("+00:00", "Z"),
        payload=payload,
        _proof=_VERIFIED_EVIDENCE_PROOF,
    )


def apply_product_github_decision(
    *,
    draft: dict[str, Any],
    decision: VerifiedGitHubDecision,
    source: GitHubEvidenceSource,
    profile: GitHubTrustProfile,
    ledger: GovernedAuthorityLedger,
    formation_request: dict[str, Any],
    formation_publication: dict[str, Any],
) -> dict[str, Any]:
    """Final-live verify and consume the exact Human decision for system transport."""

    expected_payload = formation_request.get("github_request_payload")
    if not isinstance(expected_payload, dict):
        raise PilotContractError("canonical formation request lacks GitHub payload")

    current = _utc_now().astimezone(timezone.utc)
    recording = RecordingGitHubSource(source)
    final_request = verify_formation_published_request(
        recording,
        profile=profile,
        issue_number=decision.issue_number,
        expected_payload=expected_payload,
        now=current,
    )
    final_draft = build_pilot_draft_from_formation(
        formation_request,
        final_request,
        formation_publication=formation_publication,
    )
    expected_draft = pilot_draft_sha256(final_draft)
    if expected_draft != pilot_draft_sha256(draft):
        raise PilotContractError("GitHub request changed before final live verification")

    final_decision = verify_product_github_decision(
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
        raise PilotContractError("final GitHub decision identity differs from reviewed decision")

    snapshot = build_authority_snapshot(
        recording=recording,
        request=final_request,
        decision=final_decision,
        draft_sha256=expected_draft,
    )
    snapshot["request_transport_provenance"] = copy.deepcopy(
        final_draft["request_transport_provenance"]
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
    request_transport = copy.deepcopy(final_draft.get("request_transport_provenance"))
    common = {
        "schema_version": "executor-pilot-decision-result/1.2",
        "draft_sha256": expected_draft,
        "formation_binding": formation_binding,
        "request_transport_provenance": request_transport,
        "authority_snapshot": snapshot,
        "authority_snapshot_sha256": snapshot_sha256,
        "decision_evidence": final_decision.to_dict(),
        "authority_source": "VERIFIED_HUMAN_DECISION_ONLY",
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
            "schema_version": "executor-frozen-pilot-contract/1.2",
            "request_id": final_draft["request_id"],
            "target": copy.deepcopy(final_draft["target"]),
            "task": copy.deepcopy(final_draft["task"]),
            "formation_binding": formation_binding,
            "request_transport_provenance": request_transport,
            "request_evidence": final_request.to_dict(),
            "decision_evidence": final_decision.to_dict(),
            "authority_snapshot": snapshot,
            "authority_snapshot_sha256": snapshot_sha256,
            "draft_sha256": expected_draft,
            "authority_source": "VERIFIED_HUMAN_DECISION_ONLY",
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
            "schema_version": "executor-pilot-decision-result/1.2",
            "status": "AUTHORIZED_AND_FROZEN",
            "contract": contract,
            "contract_sha256": contract_sha256,
            "draft_sha256": expected_draft,
            "formation_binding": formation_binding,
            "request_transport_provenance": request_transport,
            "authority_snapshot_sha256": snapshot_sha256,
            "decision_evidence": final_decision.to_dict(),
            "authority_source": "VERIFIED_HUMAN_DECISION_ONLY",
            "executable": True,
        }
    else:
        raise GitHubTrustError("unsupported verified GitHub decision")

    result["decision_consumption"] = ledger.bind_result(
        consumption=consumption,
        result=result,
    )
    return result
