from __future__ import annotations

import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from executor.github_effect_transaction import canonical_effect_bytes
from executor.github_trust import GitHubEvidenceSource, canonical_json, sha256_text


class FormationPublicationRecoveryError(RuntimeError):
    pass


def _load_single(directory: Path, pattern: str, *, label: str) -> tuple[Path, dict[str, Any], bytes]:
    paths = sorted(directory.glob(pattern))
    if len(paths) != 1:
        raise FormationPublicationRecoveryError(
            f"{label} requires exactly one {pattern}; found {len(paths)}"
        )
    path = paths[0]
    raw = path.read_bytes()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FormationPublicationRecoveryError(f"invalid {label} JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise FormationPublicationRecoveryError(f"{label} must be an object")
    return path, value, raw


def recover_formation_publication(
    *,
    incomplete_publication: dict[str, Any],
    evidence_directory: Path,
    source: GitHubEvidenceSource,
) -> dict[str, Any]:
    """Reconcile a confirmed CREATE_ISSUE after a false-negative immediate read-back.

    This function is read-only with respect to GitHub. It never consumes new
    authority and never repeats the external write. The original bound
    NO_EFFECT_CONFIRMED result remains historical evidence; recovery creates a
    new transport artifact from the durable 201 receipt plus a fresh exact GET.
    """

    if (
        incomplete_publication.get("schema_version")
        != "executor-formation-publication-result/1.1"
        or incomplete_publication.get("status") != "FORMATION_PUBLICATION_INCOMPLETE"
        or incomplete_publication.get("executable") is not False
        or incomplete_publication.get("manual_request_rewrite_required") is not False
    ):
        raise FormationPublicationRecoveryError("publication is not a recoverable incomplete formation result")

    canonical = incomplete_publication.get("canonical_contract_request")
    binding = incomplete_publication.get("formation_binding")
    payload = incomplete_publication.get("github_request_payload")
    effect = incomplete_publication.get("publication_effect")
    if not all(isinstance(item, dict) for item in (canonical, binding, payload, effect)):
        raise FormationPublicationRecoveryError("incomplete publication lacks canonical binding/payload/effect")
    if canonical.get("formation_binding") != binding or canonical.get("github_request_payload") != payload:
        raise FormationPublicationRecoveryError("incomplete publication canonical binding mismatch")
    if (
        effect.get("status") != "NO_EFFECT_CONFIRMED"
        or effect.get("action_kind") != "CREATE_ISSUE"
        or effect.get("target") != "FJ899/Executor"
        or effect.get("automatic_retry_allowed") is not False
    ):
        raise FormationPublicationRecoveryError("publication effect is not the bounded false-negative recovery class")

    issue_payload = {
        "schema_version": "executor-formation-authority-issue/1.0",
        "title": f"Executor authority request: {payload.get('request_id')}",
        "body": canonical_json(payload),
    }
    expected_effect_sha = hashlib.sha256(canonical_effect_bytes(issue_payload)).hexdigest()
    if effect.get("effect_sha256") != expected_effect_sha:
        raise FormationPublicationRecoveryError("incomplete publication effect hash mismatch")

    _, attempt_result, _ = _load_single(
        evidence_directory,
        "external_effect_attempt_result-*.json",
        label="attempt result",
    )
    receipt_path, receipt, receipt_raw = _load_single(
        evidence_directory,
        "system_write_receipt-*.json",
        label="system write receipt",
    )
    if attempt_result.get("kind") != "EXTERNAL_EFFECT_ATTEMPT_RESULT_BINDING":
        raise FormationPublicationRecoveryError("attempt result kind is invalid")
    attempt = attempt_result.get("payload")
    receipt_payload = receipt.get("payload")
    if receipt.get("kind") != "SYSTEM_WRITE_RECEIPT" or not isinstance(receipt_payload, dict):
        raise FormationPublicationRecoveryError("system write receipt kind/payload is invalid")
    if not isinstance(attempt, dict):
        raise FormationPublicationRecoveryError("attempt result payload is invalid")

    receipt_digest = hashlib.sha256(receipt_raw).hexdigest()
    expected_receipt_digest = receipt_path.stem.removeprefix("system_write_receipt-")
    if receipt_digest != expected_receipt_digest:
        raise FormationPublicationRecoveryError("system write receipt file hash mismatch")
    if attempt.get("receipt_evidence_sha256") != receipt_digest:
        raise FormationPublicationRecoveryError("attempt result does not bind the exact write receipt")

    for label, value in (("attempt", attempt), ("receipt", receipt_payload)):
        if (
            value.get("provider") != "GITHUB"
            or value.get("action_kind") != "CREATE_ISSUE"
            or value.get("target") != "FJ899/Executor"
            or value.get("effect_sha256") != expected_effect_sha
        ):
            raise FormationPublicationRecoveryError(f"{label} identity differs from incomplete publication")
    if (
        attempt.get("provider_outcome") != "SUCCESS"
        or attempt.get("receipt_provider_status") != 201
        or receipt_payload.get("provider_outcome") != "SUCCESS"
        or receipt_payload.get("provider_status") != 201
    ):
        raise FormationPublicationRecoveryError("durable receipt does not prove successful CREATE_ISSUE")

    object_id = attempt.get("object_id")
    object_url = attempt.get("object_url")
    if (
        not isinstance(object_id, str)
        or not object_id.isdecimal()
        or int(object_id) <= 0
        or object_id != receipt_payload.get("object_id")
        or not isinstance(object_url, str)
        or object_url != receipt_payload.get("object_url")
    ):
        raise FormationPublicationRecoveryError("attempt/receipt durable object identity mismatch")

    response_b64 = receipt.get("provider_response_b64")
    if not isinstance(response_b64, str):
        raise FormationPublicationRecoveryError("write receipt lacks provider response")
    try:
        write_response_raw = base64.b64decode(response_b64, validate=True)
        write_response = json.loads(write_response_raw.decode("utf-8"))
    except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
        raise FormationPublicationRecoveryError("write receipt provider response is invalid") from exc
    if (
        not isinstance(write_response, dict)
        or str(write_response.get("number")) != object_id
        or write_response.get("html_url") != object_url
        or write_response.get("title") != issue_payload["title"]
        or write_response.get("body") != issue_payload["body"]
    ):
        raise FormationPublicationRecoveryError("write receipt provider response differs from canonical Issue")

    issue_number = int(object_id)
    api_url = f"https://api.github.com/repos/FJ899/Executor/issues/{issue_number}"
    fresh = source.fetch_json(api_url)
    if (
        fresh.get("url") != api_url
        or fresh.get("repository_url") != "https://api.github.com/repos/FJ899/Executor"
        or fresh.get("number") != issue_number
        or "pull_request" in fresh
        or fresh.get("state") != "open"
        or fresh.get("title") != issue_payload["title"]
        or fresh.get("body") != issue_payload["body"]
        or fresh.get("html_url") != object_url
    ):
        raise FormationPublicationRecoveryError("fresh provider read does not reproduce the canonical Issue")
    node_id = fresh.get("node_id")
    provider_id = fresh.get("id")
    if not isinstance(node_id, str) or not node_id or type(provider_id) is not int:
        raise FormationPublicationRecoveryError("fresh provider Issue lacks immutable identity")

    body_sha = sha256_text(issue_payload["body"])
    observation_ref = f"github:issue:{node_id}:{body_sha}"
    recovered_effect = {
        "schema_version": "executor-github-effect-result/1.0",
        "status": "RECOVERED_EXTERNAL_EFFECT",
        "provider": "GITHUB",
        "action_kind": "CREATE_ISSUE",
        "target": "FJ899/Executor",
        "effect_sha256": expected_effect_sha,
        "attempt_id": attempt.get("attempt_id"),
        "object_id": object_id,
        "object_url": object_url,
        "observation_ref": observation_ref,
        "automatic_retry_allowed": False,
        "external_write_repeated": False,
        "recovered_from_status": "NO_EFFECT_CONFIRMED",
        "historical_authority_result_binding": copy.deepcopy(effect.get("authority_result_binding")),
    }
    transport = {
        "origin": "FORMATION_PUBLISHED_REQUEST",
        "authority": False,
        "publisher": "EXECUTOR_FORMATION",
        "provider": "GITHUB",
        "action_kind": "CREATE_ISSUE",
        "target": "FJ899/Executor",
        "object_id": object_id,
        "object_url": object_url,
        "effect_sha256": expected_effect_sha,
        "observation_ref": observation_ref,
        "human_decision_required": True,
        "recovery_class": "POST_WRITE_FALSE_NEGATIVE_READ_RECONCILIATION",
        "external_write_repeated": False,
        "historical_authority_result_unchanged": True,
    }
    return {
        "schema_version": "executor-formation-publication-result/1.1",
        "status": "AWAITING_VERIFIED_HUMAN_DECISION",
        "canonical_contract_request": copy.deepcopy(canonical),
        "formation_binding": copy.deepcopy(binding),
        "github_request_payload": copy.deepcopy(payload),
        "request_transport_provenance": transport,
        "publication_effect": recovered_effect,
        "manual_request_rewrite_required": False,
        "executable": False,
        "recovery": {
            "kind": "READ_ONLY_PROVIDER_RECONCILIATION",
            "original_publication_status": "FORMATION_PUBLICATION_INCOMPLETE",
            "original_effect_status": "NO_EFFECT_CONFIRMED",
            "original_result_sha256": (
                effect.get("authority_result_binding", {}).get("result_sha256")
                if isinstance(effect.get("authority_result_binding"), dict)
                else None
            ),
            "external_write_repeated": False,
            "fresh_provider_issue_id": provider_id,
            "fresh_provider_issue_node_id": node_id,
        },
    }
