from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


class ExternalEffectReceiptError(ValueError):
    pass


_SCHEMA_VERSION = "executor-external-effect-receipt/1.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMPLETION_CLAIMS = {
    "COMPLETED",
    "SUCCESS",
    "PASS",
    "ACTION_COMPLETED",
    "ACTION_COMPLETED_REVIEW_REQUIRED",
}
_RECEIPT_KEYS = {
    "schema_version",
    "provider",
    "action_kind",
    "target",
    "provider_status",
    "object_id",
    "object_url",
    "response_sha256",
}


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExternalEffectReceiptError(f"{field} must be a non-empty string")
    return value.strip()


def validate_external_effect_receipt(
    receipt: dict[str, Any],
    *,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
) -> dict[str, Any]:
    """Validate a provider response receipt for one exact external mutation.

    A receipt proves only that the provider returned an object identity for the
    requested mutation. It is not independent verification that the external
    state still contains that object.
    """
    if not isinstance(receipt, dict):
        raise ExternalEffectReceiptError("external effect receipt must be an object")

    actual_keys = set(receipt)
    if actual_keys != _RECEIPT_KEYS:
        missing = sorted(_RECEIPT_KEYS - actual_keys)
        additional = sorted(actual_keys - _RECEIPT_KEYS)
        raise ExternalEffectReceiptError(
            f"external effect receipt keys differ; missing={missing}, additional={additional}"
        )

    if receipt.get("schema_version") != _SCHEMA_VERSION:
        raise ExternalEffectReceiptError("unsupported external effect receipt schema")

    provider = _required_text(receipt.get("provider"), field="provider")
    action_kind = _required_text(receipt.get("action_kind"), field="action_kind")
    target = _required_text(receipt.get("target"), field="target")
    object_id = _required_text(receipt.get("object_id"), field="object_id")
    object_url = _required_text(receipt.get("object_url"), field="object_url")

    if provider != expected_provider:
        raise ExternalEffectReceiptError("external effect receipt provider mismatch")
    if action_kind != expected_action_kind:
        raise ExternalEffectReceiptError("external effect receipt action_kind mismatch")
    if target != expected_target:
        raise ExternalEffectReceiptError("external effect receipt target mismatch")

    provider_status = receipt.get("provider_status")
    if (
        not isinstance(provider_status, int)
        or isinstance(provider_status, bool)
        or provider_status < 200
        or provider_status >= 300
    ):
        raise ExternalEffectReceiptError(
            "external effect receipt requires a provider 2xx status"
        )

    parsed_url = urlparse(object_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ExternalEffectReceiptError(
            "external effect receipt object_url must be an absolute HTTPS URL"
        )

    response_sha256 = receipt.get("response_sha256")
    if (
        not isinstance(response_sha256, str)
        or _SHA256.fullmatch(response_sha256) is None
        or set(response_sha256) == {"0"}
    ):
        raise ExternalEffectReceiptError(
            "external effect receipt requires a concrete provider response SHA-256"
        )

    return {
        "schema_version": _SCHEMA_VERSION,
        "provider": provider,
        "action_kind": action_kind,
        "target": target,
        "provider_status": provider_status,
        "object_id": object_id,
        "object_url": object_url,
        "response_sha256": response_sha256,
    }


def assess_external_completion_claim(
    *,
    claimed_status: str,
    receipt: dict[str, Any] | None,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
) -> dict[str, Any]:
    """Fail closed when an external-mutation completion claim has no receipt.

    The successful outcome of this gate is deliberately
    RECEIPT_BOUND_VERIFICATION_REQUIRED, not PASS: independent readback remains
    a separate verification boundary.
    """
    if claimed_status not in _COMPLETION_CLAIMS:
        return {
            "status": "NON_COMPLETION_RESULT",
            "terminal_success": False,
            "claimed_status": claimed_status,
        }

    if receipt is None:
        return {
            "status": "UNVERIFIED_EXTERNAL_EFFECT",
            "terminal_success": False,
            "claimed_status": claimed_status,
            "reason": "MISSING_AUTHORITATIVE_PROVIDER_RECEIPT",
        }

    try:
        normalized = validate_external_effect_receipt(
            receipt,
            expected_provider=expected_provider,
            expected_action_kind=expected_action_kind,
            expected_target=expected_target,
        )
    except ExternalEffectReceiptError as exc:
        return {
            "status": "UNVERIFIED_EXTERNAL_EFFECT",
            "terminal_success": False,
            "claimed_status": claimed_status,
            "reason": "INVALID_AUTHORITATIVE_PROVIDER_RECEIPT",
            "detail": str(exc),
        }

    return {
        "status": "RECEIPT_BOUND_VERIFICATION_REQUIRED",
        "terminal_success": False,
        "claimed_status": claimed_status,
        "receipt": normalized,
    }
