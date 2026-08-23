from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


class ExternalEffectReceiptError(ValueError):
    pass


_SCHEMA_VERSION = "executor-external-effect-receipt/1.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_KEYS = {
    "schema_version",
    "provider",
    "actor",
    "action_kind",
    "target",
    "provider_status",
    "provider_message",
    "object_id",
    "object_url",
    "response_sha256",
}


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExternalEffectReceiptError(f"{field} must be a non-empty string")
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ExternalEffectReceiptError(f"{field} must be null or a non-empty string")
    return value.strip()


def validate_system_write_receipt(
    receipt: dict[str, Any],
    *,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
) -> dict[str, Any]:
    """Validate one authoritative provider response for a SYSTEM write attempt.

    Both success and failure provider responses are receipts. A successful write
    requires durable provider object identity. A failed write must not invent an
    object identity that the provider did not create.
    """
    if not isinstance(receipt, dict):
        raise ExternalEffectReceiptError("system write receipt must be an object")

    actual_keys = set(receipt)
    if actual_keys != _RECEIPT_KEYS:
        missing = sorted(_RECEIPT_KEYS - actual_keys)
        additional = sorted(actual_keys - _RECEIPT_KEYS)
        raise ExternalEffectReceiptError(
            f"system write receipt keys differ; missing={missing}, additional={additional}"
        )

    if receipt.get("schema_version") != _SCHEMA_VERSION:
        raise ExternalEffectReceiptError("unsupported system write receipt schema")

    provider = _required_text(receipt.get("provider"), field="provider")
    actor = _required_text(receipt.get("actor"), field="actor")
    action_kind = _required_text(receipt.get("action_kind"), field="action_kind")
    target = _required_text(receipt.get("target"), field="target")
    provider_message = _required_text(
        receipt.get("provider_message"), field="provider_message"
    )
    object_id = _optional_text(receipt.get("object_id"), field="object_id")
    object_url = _optional_text(receipt.get("object_url"), field="object_url")

    if provider != expected_provider:
        raise ExternalEffectReceiptError("system write receipt provider mismatch")
    if actor != "SYSTEM":
        raise ExternalEffectReceiptError("system write receipt actor must be SYSTEM")
    if action_kind != expected_action_kind:
        raise ExternalEffectReceiptError("system write receipt action_kind mismatch")
    if target != expected_target:
        raise ExternalEffectReceiptError("system write receipt target mismatch")

    provider_status = receipt.get("provider_status")
    if (
        not isinstance(provider_status, int)
        or isinstance(provider_status, bool)
        or provider_status < 100
        or provider_status > 599
    ):
        raise ExternalEffectReceiptError("provider_status must be an HTTP status integer")

    response_sha256 = receipt.get("response_sha256")
    if (
        not isinstance(response_sha256, str)
        or _SHA256.fullmatch(response_sha256) is None
        or set(response_sha256) == {"0"}
    ):
        raise ExternalEffectReceiptError(
            "system write receipt requires a concrete provider response SHA-256"
        )

    success = 200 <= provider_status < 300
    if success:
        if object_id is None or object_url is None:
            raise ExternalEffectReceiptError(
                "successful system write requires durable provider object identity"
            )
        parsed_url = urlparse(object_url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise ExternalEffectReceiptError(
                "successful system write object_url must be an absolute HTTPS URL"
            )
    elif object_id is not None or object_url is not None:
        raise ExternalEffectReceiptError(
            "failed system write receipt must not claim created object identity"
        )

    return {
        "schema_version": _SCHEMA_VERSION,
        "provider": provider,
        "actor": actor,
        "action_kind": action_kind,
        "target": target,
        "provider_status": provider_status,
        "provider_message": provider_message,
        "object_id": object_id,
        "object_url": object_url,
        "response_sha256": response_sha256,
        "provider_outcome": "SUCCESS" if success else "FAILURE",
    }


def assess_system_write(
    *,
    receipt: dict[str, Any] | None,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
) -> dict[str, Any]:
    """Apply INV-AR1 to a system-performed mutating action."""
    if receipt is None:
        return {
            "system_write": "UNVERIFIED",
            "system_receipt": "MISSING",
            "system_completion": False,
            "terminal_success": False,
            "reason": "NO_RECEIPT_NO_SYSTEM_COMPLETION_CLAIM",
        }

    try:
        normalized = validate_system_write_receipt(
            receipt,
            expected_provider=expected_provider,
            expected_action_kind=expected_action_kind,
            expected_target=expected_target,
        )
    except ExternalEffectReceiptError as exc:
        return {
            "system_write": "UNVERIFIED",
            "system_receipt": "INVALID",
            "system_completion": False,
            "terminal_success": False,
            "reason": "INVALID_AUTHORITATIVE_SYSTEM_RECEIPT",
            "detail": str(exc),
        }

    if normalized["provider_outcome"] == "FAILURE":
        return {
            "system_write": "FAILED",
            "system_receipt": "AUTHORITATIVE_FAILURE_RECEIPT",
            "system_completion": False,
            "terminal_success": False,
            "receipt": normalized,
        }

    return {
        "system_write": "COMPLETED",
        "system_receipt": "AUTHORITATIVE_SUCCESS_RECEIPT",
        "system_completion": True,
        "terminal_success": False,
        "verification": "INDEPENDENT_READ_REQUIRED",
        "receipt": normalized,
    }


def assess_actor_receipt_provenance(
    *,
    system_receipt: dict[str, Any] | None,
    human_write_claim: bool,
    independent_read_observed: bool,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
) -> dict[str, Any]:
    """Apply INV-AR1..AR3 across SYSTEM and HUMAN provenance boundaries.

    A human report is a new actor event. It never inherits the status or receipt
    of the earlier system attempt. Independent observation may change the human
    event's verification state, but cannot retroactively rewrite system history.
    """
    system = assess_system_write(
        receipt=system_receipt,
        expected_provider=expected_provider,
        expected_action_kind=expected_action_kind,
        expected_target=expected_target,
    )

    if not human_write_claim:
        return {
            "system": system,
            "human_write": "NOT_REPORTED",
            "current_result": system["system_write"],
            "terminal_pass": False,
        }

    human_state = "OBSERVED" if independent_read_observed else "UNVERIFIED"
    return {
        "system": system,
        "human_write": "HUMAN_REPORTED",
        "human_verification": human_state,
        "current_result": f"HUMAN_REPORTED / {human_state}",
        "terminal_pass": False,
        "provenance_rule": "HUMAN_CLAIM_MUST_NOT_INHERIT_SYSTEM_COMPLETION",
        "evidence_non_substitution": True,
    }
