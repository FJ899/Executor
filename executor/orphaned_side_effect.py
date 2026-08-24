from __future__ import annotations

import base64
import binascii
import json
import os
import re
import secrets
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .external_effect_receipt import (
    ExternalEffectReceiptError,
    VerifiedExternalEffectReceipt,
    _canonical_json_bytes,
    _parse_utc,
    _persist_verified_system_write_receipt,
    _read_regular_file,
    _required_bytes,
    _required_text,
    _sha256_bytes,
    _validate_expected_identity,
    _validate_provider_object_binding,
    _validate_provider_target,
    _validate_sha256,
    assess_system_write,
)


_RECOVERY_SCHEMA_VERSION = "executor-orphaned-side-effect/1.2"
_RECOVERY_EVIDENCE_SCHEMA_VERSION = "executor-orphaned-side-effect-evidence/1.2"
_ATTEMPT_ID = re.compile(r"^ose-[0-9a-f]{32}$")
_VERIFIED_ATTEMPT_PROOF = object()
_VERIFIED_SCAN_PROOF = object()
_VERIFIED_BOUND_RECEIPT_PROOF = object()

# A provider error response is only a clean no-effect failure when this bounded
# integration has explicit semantics for it. 5xx and all unclassified statuses
# remain ambiguous because the external mutation may have happened upstream.
_GITHUB_DEFINITIVE_NO_EFFECT_STATUSES = frozenset(
    {400, 401, 403, 404, 405, 409, 410, 415, 422, 429}
)


class OrphanedSideEffectRecoveryRequired(RuntimeError):
    """A provider write result cannot be durably bound to its exact attempt."""


__all__ = [
    "OrphanedSideEffectRecoveryRequired",
    "VerifiedExternalEffectAttempt",
    "VerifiedExternalRecoveryScan",
    "VerifiedAttemptBoundReceipt",
    "assess_orphaned_side_effect_recovery",
]


def _validate_attempt_id(value: object) -> str:
    text = _required_text(value, field="attempt_id")
    if _ATTEMPT_ID.fullmatch(text) is None:
        raise ExternalEffectReceiptError(
            "attempt_id must use ose- followed by 32 lowercase hex characters"
        )
    return text


def _mint_attempt_id() -> str:
    """Mint the recovery correlation nonce inside the trusted pre-write boundary."""
    return _validate_attempt_id(f"ose-{secrets.token_hex(16)}")


def _utc_datetime(value: object, *, field: str) -> datetime:
    text = _parse_utc(value, field=field)
    return datetime.fromisoformat(text[:-1] + "+00:00")


def _strict_json_bytes(value: bytes, *, field: str) -> dict[str, Any]:
    value = _required_bytes(value, field=field)

    def pairs(pairs_value: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs_value:
            if key in result:
                raise ExternalEffectReceiptError(
                    f"{field} contains duplicate JSON key: {key}"
                )
            result[key] = item
        return result

    try:
        parsed = json.loads(value.decode("utf-8"), object_pairs_hook=pairs)
    except UnicodeError as exc:
        raise ExternalEffectReceiptError(f"{field} must be UTF-8 JSON") from exc
    except json.JSONDecodeError as exc:
        raise ExternalEffectReceiptError(f"{field} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ExternalEffectReceiptError(f"{field} must contain a JSON object")
    return parsed


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _ensure_durable_evidence_directory(value: str | Path) -> Path:
    """Create an evidence directory and durably bind every newly created entry."""
    path = Path(value)
    if path.exists() and path.is_symlink():
        raise ExternalEffectReceiptError("evidence_directory must not be a symlink")

    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        parent = cursor.parent
        if parent == cursor:
            raise ExternalEffectReceiptError(
                "cannot locate an existing parent for evidence_directory"
            )
        cursor = parent

    if cursor.is_symlink() or not cursor.is_dir():
        raise ExternalEffectReceiptError(
            "existing evidence_directory ancestor must be a real directory"
        )

    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if directory.is_symlink() or not directory.is_dir():
                raise ExternalEffectReceiptError(
                    "evidence_directory creation raced with a non-directory"
                )
        _fsync_directory(directory)
        _fsync_directory(directory.parent)

    if path.is_symlink():
        raise ExternalEffectReceiptError("evidence_directory must not be a symlink")
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ExternalEffectReceiptError("evidence_directory must be a directory")

    _fsync_directory(resolved)
    _fsync_directory(resolved.parent)
    return resolved


def _persist_record(
    *,
    kind: str,
    payload: dict[str, Any],
    evidence_directory: str | Path,
    raw_response: bytes | None = None,
) -> tuple[str, str]:
    directory = _ensure_durable_evidence_directory(evidence_directory)
    envelope: dict[str, Any] = {
        "schema_version": _RECOVERY_EVIDENCE_SCHEMA_VERSION,
        "kind": kind,
        "payload": payload,
    }
    if raw_response is not None:
        raw_response = _required_bytes(raw_response, field="raw_response")
        envelope["raw_response_b64"] = base64.b64encode(raw_response).decode("ascii")

    encoded = _canonical_json_bytes(envelope)
    evidence_sha256 = _sha256_bytes(encoded)
    final_path = directory / f"{kind.lower()}-{evidence_sha256}.json"

    if final_path.exists():
        if _read_regular_file(final_path) != encoded:
            raise ExternalEffectReceiptError(
                "content-addressed orphaned-side-effect evidence collision"
            )
    else:
        fd, temporary_name = tempfile.mkstemp(
            prefix=".orphaned-side-effect-",
            suffix=".tmp",
            dir=directory,
        )
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, final_path)
            _fsync_directory(directory)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    persisted = _read_regular_file(final_path)
    if persisted != encoded or _sha256_bytes(persisted) != evidence_sha256:
        raise ExternalEffectReceiptError(
            "persisted orphaned-side-effect evidence failed read-after-write verification"
        )
    return str(final_path), evidence_sha256


def _persist_unique_attempt_record(
    *,
    payload: dict[str, Any],
    evidence_directory: str | Path,
) -> tuple[str, str]:
    """Atomically reserve attempt_id and persist its full pre-write journal."""
    directory = _ensure_durable_evidence_directory(evidence_directory)
    attempt_id = _validate_attempt_id(payload.get("attempt_id"))
    envelope = {
        "schema_version": _RECOVERY_EVIDENCE_SCHEMA_VERSION,
        "kind": "EXTERNAL_EFFECT_ATTEMPT",
        "payload": payload,
    }
    encoded = _canonical_json_bytes(envelope)
    evidence_sha256 = _sha256_bytes(encoded)
    final_path = directory / f"external_effect_attempt-{attempt_id}.json"

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(final_path, flags, 0o600)
    except FileExistsError as exc:
        raise ExternalEffectReceiptError(
            f"attempt_id already reserved in this evidence root: {attempt_id}"
        ) from exc
    except OSError as exc:
        raise ExternalEffectReceiptError(
            f"could not reserve attempt_id before provider write: {attempt_id}"
        ) from exc

    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)

    _fsync_directory(directory)
    persisted = _read_regular_file(final_path)
    if persisted != encoded or _sha256_bytes(persisted) != evidence_sha256:
        raise ExternalEffectReceiptError(
            "persisted pre-write attempt failed read-after-write verification"
        )
    return str(final_path), evidence_sha256


def _persist_unique_attempt_result_record(
    *,
    attempt_id: str,
    payload: dict[str, Any],
    evidence_directory: Path,
) -> tuple[str, str]:
    """Persist one immutable result-binding slot for one attempt.

    An identical second finalization is idempotent. A different result for the
    same attempt is a provenance conflict and must fail closed.
    """
    attempt_id = _validate_attempt_id(attempt_id)
    envelope = {
        "schema_version": _RECOVERY_EVIDENCE_SCHEMA_VERSION,
        "kind": "EXTERNAL_EFFECT_ATTEMPT_RESULT_BINDING",
        "payload": payload,
    }
    encoded = _canonical_json_bytes(envelope)
    evidence_sha256 = _sha256_bytes(encoded)
    final_path = evidence_directory / f"external_effect_attempt_result-{attempt_id}.json"

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(final_path, flags, 0o600)
    except FileExistsError:
        existing = _read_regular_file(final_path)
        if existing != encoded:
            raise ExternalEffectReceiptError(
                "conflicting provider result already bound to this attempt_id"
            )
        return str(final_path), evidence_sha256
    except OSError as exc:
        raise ExternalEffectReceiptError(
            f"could not reserve result slot for attempt_id: {attempt_id}"
        ) from exc

    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)

    _fsync_directory(evidence_directory)
    persisted = _read_regular_file(final_path)
    if persisted != encoded or _sha256_bytes(persisted) != evidence_sha256:
        raise ExternalEffectReceiptError(
            "persisted attempt-result binding failed read-after-write verification"
        )
    return str(final_path), evidence_sha256


def _read_verified_record(
    *,
    kind: str,
    payload: dict[str, Any],
    evidence_ref: str,
    evidence_sha256: str,
) -> bytes | None:
    evidence_sha256 = _validate_sha256(evidence_sha256, field="evidence_sha256")
    path = Path(_required_text(evidence_ref, field="evidence_ref"))
    encoded = _read_regular_file(path)
    if _sha256_bytes(encoded) != evidence_sha256:
        raise ExternalEffectReceiptError(
            "persisted orphaned-side-effect evidence hash mismatch"
        )
    envelope = _strict_json_bytes(encoded, field="persisted recovery evidence")
    if (
        envelope.get("schema_version") != _RECOVERY_EVIDENCE_SCHEMA_VERSION
        or envelope.get("kind") != kind
        or envelope.get("payload") != payload
    ):
        raise ExternalEffectReceiptError(
            "persisted orphaned-side-effect evidence does not bind the verified object"
        )

    raw_b64 = envelope.get("raw_response_b64")
    if raw_b64 is None:
        return None
    if not isinstance(raw_b64, str):
        raise ExternalEffectReceiptError("persisted recovery response encoding is invalid")
    try:
        return base64.b64decode(raw_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ExternalEffectReceiptError(
            "persisted recovery response encoding is invalid"
        ) from exc


def _record_root(evidence_ref: str) -> Path:
    path = Path(_required_text(evidence_ref, field="evidence_ref"))
    try:
        return path.parent.resolve(strict=True)
    except OSError as exc:
        raise ExternalEffectReceiptError("evidence root is unavailable") from exc


def _attempt_root(attempt: "VerifiedExternalEffectAttempt") -> Path:
    return _record_root(attempt.attempt_ref)


def _require_attempt_root(
    attempt: "VerifiedExternalEffectAttempt", evidence_directory: str | Path
) -> Path:
    expected = _attempt_root(attempt)
    candidate = Path(evidence_directory)
    try:
        actual = candidate.resolve(strict=True)
    except OSError as exc:
        raise ExternalEffectReceiptError(
            "provider result evidence_directory must already be the attempt evidence root"
        ) from exc
    if actual != expected:
        raise ExternalEffectReceiptError(
            "provider result evidence_directory does not match attempt evidence root"
        )
    return expected


@dataclass(frozen=True)
class VerifiedExternalEffectAttempt:
    provider: str
    action_kind: str
    target: str
    attempt_id: str
    effect_sha256: str
    started_at: str
    attempt_state: str
    retry_policy: str
    attempt_ref: str
    evidence_sha256: str
    _proof: object = field(repr=False, compare=False, init=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _VERIFIED_ATTEMPT_PROOF:
            raise ExternalEffectReceiptError(
                "VerifiedExternalEffectAttempt must be minted before the provider write"
            )

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "schema_version": _RECOVERY_SCHEMA_VERSION,
            "provider": self.provider,
            "actor": "SYSTEM",
            "action_kind": self.action_kind,
            "target": self.target,
            "attempt_id": self.attempt_id,
            "effect_sha256": self.effect_sha256,
            "started_at": self.started_at,
            "attempt_state": self.attempt_state,
            "retry_policy": self.retry_policy,
        }


@dataclass(frozen=True)
class _RecoveryCandidate:
    object_id: str
    object_url: str
    effect_sha256: str
    correlation_id: str | None
    created_at: str

    def payload(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_url": self.object_url,
            "effect_sha256": self.effect_sha256,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class VerifiedExternalRecoveryScan:
    provider: str
    action_kind: str
    target: str
    scanned_at: str
    complete: bool
    candidates: tuple[_RecoveryCandidate, ...]
    response_sha256: str
    scan_ref: str
    evidence_sha256: str
    _proof: object = field(repr=False, compare=False, init=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _VERIFIED_SCAN_PROOF:
            raise ExternalEffectReceiptError(
                "VerifiedExternalRecoveryScan must be minted by the trusted recovery verifier"
            )

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "schema_version": _RECOVERY_SCHEMA_VERSION,
            "provider": self.provider,
            "actor": "RECOVERY_VERIFIER",
            "action_kind": self.action_kind,
            "target": self.target,
            "scanned_at": self.scanned_at,
            "complete": self.complete,
            "candidates": [candidate.payload() for candidate in self.candidates],
            "response_sha256": self.response_sha256,
        }


@dataclass(frozen=True)
class VerifiedAttemptBoundReceipt:
    attempt_id: str
    attempt_evidence_sha256: str
    receipt: VerifiedExternalEffectReceipt
    binding_ref: str
    evidence_sha256: str
    _proof: object = field(repr=False, compare=False, init=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _VERIFIED_BOUND_RECEIPT_PROOF:
            raise ExternalEffectReceiptError(
                "VerifiedAttemptBoundReceipt must be minted by the attempt result finalizer"
            )

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "schema_version": _RECOVERY_SCHEMA_VERSION,
            "provider": self.receipt.provider,
            "actor": "SYSTEM",
            "action_kind": self.receipt.action_kind,
            "target": self.receipt.target,
            "attempt_id": self.attempt_id,
            "attempt_evidence_sha256": self.attempt_evidence_sha256,
            "effect_sha256": self.receipt.effect_sha256,
            "receipt_ref": self.receipt.receipt_ref,
            "receipt_evidence_sha256": self.receipt.evidence_sha256,
            "receipt_response_sha256": self.receipt.response_sha256,
            "receipt_provider_status": self.receipt.provider_status,
            "receipt_provider_message": self.receipt.provider_message,
            "provider_outcome": self.receipt.provider_outcome,
            "object_id": self.receipt.object_id,
            "object_url": self.receipt.object_url,
        }


def _mint_attempt(
    *, payload: dict[str, Any], attempt_ref: str, evidence_sha256: str
) -> VerifiedExternalEffectAttempt:
    instance = object.__new__(VerifiedExternalEffectAttempt)
    for key in (
        "provider",
        "action_kind",
        "target",
        "attempt_id",
        "effect_sha256",
        "started_at",
        "attempt_state",
        "retry_policy",
    ):
        object.__setattr__(instance, key, payload[key])
    object.__setattr__(instance, "attempt_ref", attempt_ref)
    object.__setattr__(instance, "evidence_sha256", evidence_sha256)
    object.__setattr__(instance, "_proof", _VERIFIED_ATTEMPT_PROOF)
    return instance


def _mint_scan(
    *, payload: dict[str, Any], scan_ref: str, evidence_sha256: str
) -> VerifiedExternalRecoveryScan:
    instance = object.__new__(VerifiedExternalRecoveryScan)
    for key in ("provider", "action_kind", "target", "scanned_at", "complete"):
        object.__setattr__(instance, key, payload[key])
    candidates = tuple(
        _RecoveryCandidate(
            object_id=item["object_id"],
            object_url=item["object_url"],
            effect_sha256=item["effect_sha256"],
            correlation_id=item["correlation_id"],
            created_at=item["created_at"],
        )
        for item in payload["candidates"]
    )
    object.__setattr__(instance, "candidates", candidates)
    object.__setattr__(instance, "response_sha256", payload["response_sha256"])
    object.__setattr__(instance, "scan_ref", scan_ref)
    object.__setattr__(instance, "evidence_sha256", evidence_sha256)
    object.__setattr__(instance, "_proof", _VERIFIED_SCAN_PROOF)
    return instance


def _mint_attempt_bound_receipt(
    *,
    attempt: VerifiedExternalEffectAttempt,
    receipt: VerifiedExternalEffectReceipt,
    binding_ref: str,
    evidence_sha256: str,
) -> VerifiedAttemptBoundReceipt:
    instance = object.__new__(VerifiedAttemptBoundReceipt)
    object.__setattr__(instance, "attempt_id", attempt.attempt_id)
    object.__setattr__(instance, "attempt_evidence_sha256", attempt.evidence_sha256)
    object.__setattr__(instance, "receipt", receipt)
    object.__setattr__(instance, "binding_ref", binding_ref)
    object.__setattr__(instance, "evidence_sha256", evidence_sha256)
    object.__setattr__(instance, "_proof", _VERIFIED_BOUND_RECEIPT_PROOF)
    return instance


def _persist_external_effect_attempt(
    *,
    provider: str,
    action_kind: str,
    target: str,
    effect_bytes: bytes,
    started_at: str,
    evidence_directory: str | Path,
) -> VerifiedExternalEffectAttempt:
    """Mint, reserve and persist the ambiguity journal before provider entry."""
    provider = _required_text(provider, field="provider")
    action_kind = _required_text(action_kind, field="action_kind")
    target = _required_text(target, field="target")
    effect_bytes = _required_bytes(effect_bytes, field="effect_bytes")
    started_at = _parse_utc(started_at, field="started_at")
    _validate_provider_target(provider=provider, action_kind=action_kind, target=target)

    attempt_id = _mint_attempt_id()
    payload = {
        "schema_version": _RECOVERY_SCHEMA_VERSION,
        "provider": provider,
        "actor": "SYSTEM",
        "action_kind": action_kind,
        "target": target,
        "attempt_id": attempt_id,
        "effect_sha256": _sha256_bytes(effect_bytes),
        "started_at": started_at,
        "attempt_state": "WRITE_IN_FLIGHT",
        "retry_policy": "FORBIDDEN_WHILE_UNRESOLVED",
    }
    attempt_ref, evidence_sha256 = _persist_unique_attempt_record(
        payload=payload,
        evidence_directory=evidence_directory,
    )
    return _mint_attempt(
        payload=payload,
        attempt_ref=attempt_ref,
        evidence_sha256=evidence_sha256,
    )


def validate_external_effect_attempt(
    attempt: VerifiedExternalEffectAttempt,
    *,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
    expected_effect_sha256: str,
) -> VerifiedExternalEffectAttempt:
    if not isinstance(attempt, VerifiedExternalEffectAttempt):
        raise ExternalEffectReceiptError(
            "recovery requires a VerifiedExternalEffectAttempt"
        )
    _validate_expected_identity(
        provider=attempt.provider,
        action_kind=attempt.action_kind,
        target=attempt.target,
        expected_provider=expected_provider,
        expected_action_kind=expected_action_kind,
        expected_target=expected_target,
    )
    _validate_attempt_id(attempt.attempt_id)
    _parse_utc(attempt.started_at, field="started_at")
    if attempt.effect_sha256 != _validate_sha256(
        expected_effect_sha256, field="expected_effect_sha256"
    ):
        raise ExternalEffectReceiptError("attempt effect fingerprint mismatch")
    if attempt.attempt_state != "WRITE_IN_FLIGHT":
        raise ExternalEffectReceiptError("attempt state is not WRITE_IN_FLIGHT")
    if attempt.retry_policy != "FORBIDDEN_WHILE_UNRESOLVED":
        raise ExternalEffectReceiptError("attempt retry policy is not fail-closed")
    raw = _read_verified_record(
        kind="EXTERNAL_EFFECT_ATTEMPT",
        payload=attempt.evidence_payload(),
        evidence_ref=attempt.attempt_ref,
        evidence_sha256=attempt.evidence_sha256,
    )
    if raw is not None:
        raise ExternalEffectReceiptError(
            "pre-write attempt evidence must not contain a provider response"
        )
    return attempt


def _normalize_scan_response(
    *,
    scan_response: bytes,
    provider: str,
    action_kind: str,
    target: str,
    scanned_at: str,
) -> dict[str, Any]:
    provider = _required_text(provider, field="provider")
    action_kind = _required_text(action_kind, field="action_kind")
    target = _required_text(target, field="target")
    scanned_at = _parse_utc(scanned_at, field="scanned_at")
    scanned_dt = _utc_datetime(scanned_at, field="scanned_at")
    _validate_provider_target(provider=provider, action_kind=action_kind, target=target)

    raw = _strict_json_bytes(scan_response, field="scan_response")
    if set(raw) != {"complete", "objects"}:
        raise ExternalEffectReceiptError(
            "scan_response must contain exactly complete and objects"
        )
    complete = raw["complete"]
    if type(complete) is not bool:
        raise ExternalEffectReceiptError("scan_response.complete must be a boolean")
    objects = raw["objects"]
    if not isinstance(objects, list):
        raise ExternalEffectReceiptError("scan_response.objects must be a list")

    candidates: list[dict[str, Any]] = []
    seen_objects: set[tuple[str, str]] = set()
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            raise ExternalEffectReceiptError(
                f"scan_response.objects[{index}] must be an object"
            )
        if set(item) != {"id", "html_url", "body", "correlation_id", "created_at"}:
            raise ExternalEffectReceiptError(
                f"scan_response.objects[{index}] has unexpected or missing fields"
            )
        object_id_value = item["id"]
        if (
            not isinstance(object_id_value, int)
            or isinstance(object_id_value, bool)
            or object_id_value <= 0
        ):
            raise ExternalEffectReceiptError(
                f"scan_response.objects[{index}].id must be a positive integer"
            )
        object_id = str(object_id_value)
        object_url = _required_text(
            item["html_url"], field=f"scan_response.objects[{index}].html_url"
        )
        body_value = item["body"]
        if not isinstance(body_value, str):
            raise ExternalEffectReceiptError(
                f"scan_response.objects[{index}].body must be a string"
            )
        correlation_value = item["correlation_id"]
        correlation_id: str | None
        if correlation_value is None:
            correlation_id = None
        else:
            correlation_id = _validate_attempt_id(correlation_value)
        created_at = _parse_utc(
            item["created_at"], field=f"scan_response.objects[{index}].created_at"
        )
        if _utc_datetime(created_at, field="created_at") > scanned_dt:
            raise ExternalEffectReceiptError(
                "recovery scan cannot observe an object created after scanned_at"
            )

        _validate_provider_object_binding(
            provider=provider,
            action_kind=action_kind,
            target=target,
            object_id=object_id,
            object_url=object_url,
        )
        object_key = (object_id, object_url)
        if object_key in seen_objects:
            raise ExternalEffectReceiptError(
                "scan_response contains duplicate provider object identity"
            )
        seen_objects.add(object_key)
        candidates.append(
            {
                "object_id": object_id,
                "object_url": object_url,
                "effect_sha256": _sha256_bytes(body_value.encode("utf-8")),
                "correlation_id": correlation_id,
                "created_at": created_at,
            }
        )

    return {
        "schema_version": _RECOVERY_SCHEMA_VERSION,
        "provider": provider,
        "actor": "RECOVERY_VERIFIER",
        "action_kind": action_kind,
        "target": target,
        "scanned_at": scanned_at,
        "complete": complete,
        "candidates": candidates,
        "response_sha256": _sha256_bytes(scan_response),
    }


def _persist_verified_external_recovery_scan(
    *,
    scan_response: bytes,
    evidence_directory: str | Path,
    provider: str,
    action_kind: str,
    target: str,
    scanned_at: str,
) -> VerifiedExternalRecoveryScan:
    scan_response = _required_bytes(scan_response, field="scan_response")
    payload = _normalize_scan_response(
        scan_response=scan_response,
        provider=provider,
        action_kind=action_kind,
        target=target,
        scanned_at=scanned_at,
    )
    scan_ref, evidence_sha256 = _persist_record(
        kind="EXTERNAL_EFFECT_RECOVERY_SCAN",
        payload=payload,
        raw_response=scan_response,
        evidence_directory=evidence_directory,
    )
    return _mint_scan(payload=payload, scan_ref=scan_ref, evidence_sha256=evidence_sha256)


def validate_external_recovery_scan(
    scan: VerifiedExternalRecoveryScan,
    *,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
) -> VerifiedExternalRecoveryScan:
    if not isinstance(scan, VerifiedExternalRecoveryScan):
        raise ExternalEffectReceiptError(
            "recovery requires a VerifiedExternalRecoveryScan"
        )
    _validate_expected_identity(
        provider=scan.provider,
        action_kind=scan.action_kind,
        target=scan.target,
        expected_provider=expected_provider,
        expected_action_kind=expected_action_kind,
        expected_target=expected_target,
    )
    _parse_utc(scan.scanned_at, field="scanned_at")
    if type(scan.complete) is not bool:
        raise ExternalEffectReceiptError("recovery scan complete must be a boolean")
    _validate_sha256(scan.response_sha256, field="response_sha256")
    raw_response = _read_verified_record(
        kind="EXTERNAL_EFFECT_RECOVERY_SCAN",
        payload=scan.evidence_payload(),
        evidence_ref=scan.scan_ref,
        evidence_sha256=scan.evidence_sha256,
    )
    if raw_response is None:
        raise ExternalEffectReceiptError(
            "verified recovery scan is missing raw scan response bytes"
        )
    normalized = _normalize_scan_response(
        scan_response=raw_response,
        provider=scan.provider,
        action_kind=scan.action_kind,
        target=scan.target,
        scanned_at=scan.scanned_at,
    )
    if normalized != scan.evidence_payload():
        raise ExternalEffectReceiptError(
            "verified recovery scan is not derived from persisted scan response bytes"
        )
    return scan


def _persist_attempt_receipt_binding(
    *,
    attempt: VerifiedExternalEffectAttempt,
    receipt: VerifiedExternalEffectReceipt,
    evidence_directory: str | Path,
) -> VerifiedAttemptBoundReceipt:
    directory = _require_attempt_root(attempt, evidence_directory)
    payload = {
        "schema_version": _RECOVERY_SCHEMA_VERSION,
        "provider": receipt.provider,
        "actor": "SYSTEM",
        "action_kind": receipt.action_kind,
        "target": receipt.target,
        "attempt_id": attempt.attempt_id,
        "attempt_evidence_sha256": attempt.evidence_sha256,
        "effect_sha256": receipt.effect_sha256,
        "receipt_ref": receipt.receipt_ref,
        "receipt_evidence_sha256": receipt.evidence_sha256,
        "receipt_response_sha256": receipt.response_sha256,
        "receipt_provider_status": receipt.provider_status,
        "receipt_provider_message": receipt.provider_message,
        "provider_outcome": receipt.provider_outcome,
        "object_id": receipt.object_id,
        "object_url": receipt.object_url,
    }
    binding_ref, evidence_sha256 = _persist_unique_attempt_result_record(
        attempt_id=attempt.attempt_id,
        payload=payload,
        evidence_directory=directory,
    )
    return _mint_attempt_bound_receipt(
        attempt=attempt,
        receipt=receipt,
        binding_ref=binding_ref,
        evidence_sha256=evidence_sha256,
    )


def validate_attempt_bound_receipt(
    bound: VerifiedAttemptBoundReceipt,
    *,
    attempt: VerifiedExternalEffectAttempt,
) -> VerifiedExternalEffectReceipt:
    if not isinstance(bound, VerifiedAttemptBoundReceipt):
        raise ExternalEffectReceiptError(
            "system receipt is not durably bound to this external-effect attempt"
        )
    if bound.attempt_id != attempt.attempt_id:
        raise ExternalEffectReceiptError("system receipt attempt_id mismatch")
    if bound.attempt_evidence_sha256 != attempt.evidence_sha256:
        raise ExternalEffectReceiptError("system receipt attempt evidence mismatch")

    attempt_root = _attempt_root(attempt)
    expected_binding_name = f"external_effect_attempt_result-{attempt.attempt_id}.json"
    binding_path = Path(bound.binding_ref)
    if binding_path.name != expected_binding_name or _record_root(bound.binding_ref) != attempt_root:
        raise ExternalEffectReceiptError(
            "attempt-result binding is not in the exact immutable attempt slot"
        )

    receipt = bound.receipt
    if not isinstance(receipt, VerifiedExternalEffectReceipt):
        raise ExternalEffectReceiptError("bound system receipt is invalid")
    if _record_root(receipt.receipt_ref) != attempt_root:
        raise ExternalEffectReceiptError(
            "bound system receipt is not stored in the attempt evidence root"
        )
    if (
        receipt.provider != attempt.provider
        or receipt.action_kind != attempt.action_kind
        or receipt.target != attempt.target
        or receipt.effect_sha256 != attempt.effect_sha256
    ):
        raise ExternalEffectReceiptError(
            "bound system receipt does not match the persisted attempt identity"
        )
    raw = _read_verified_record(
        kind="EXTERNAL_EFFECT_ATTEMPT_RESULT_BINDING",
        payload=bound.evidence_payload(),
        evidence_ref=bound.binding_ref,
        evidence_sha256=bound.evidence_sha256,
    )
    if raw is not None:
        raise ExternalEffectReceiptError(
            "attempt-result binding must not contain independent provider response bytes"
        )
    return receipt


def _persist_provider_result_for_attempt(
    *,
    attempt: VerifiedExternalEffectAttempt,
    provider_response: bytes,
    effect_bytes: bytes,
    evidence_directory: str | Path,
    provider_status: int,
    provider_message: str,
    object_id: str | None = None,
    object_url: str | None = None,
) -> VerifiedAttemptBoundReceipt:
    """Persist provider receipt, then durably bind it to the exact attempt."""
    validate_external_effect_attempt(
        attempt,
        expected_provider=attempt.provider,
        expected_action_kind=attempt.action_kind,
        expected_target=attempt.target,
        expected_effect_sha256=attempt.effect_sha256,
    )
    effect_bytes = _required_bytes(effect_bytes, field="effect_bytes")
    if _sha256_bytes(effect_bytes) != attempt.effect_sha256:
        raise ExternalEffectReceiptError(
            "provider result effect bytes do not match the persisted attempt"
        )
    try:
        directory = _require_attempt_root(attempt, evidence_directory)
        receipt = _persist_verified_system_write_receipt(
            provider_response=provider_response,
            effect_bytes=effect_bytes,
            evidence_directory=directory,
            provider=attempt.provider,
            action_kind=attempt.action_kind,
            target=attempt.target,
            provider_status=provider_status,
            provider_message=provider_message,
            object_id=object_id,
            object_url=object_url,
        )
        return _persist_attempt_receipt_binding(
            attempt=attempt,
            receipt=receipt,
            evidence_directory=directory,
        )
    except Exception as exc:
        raise OrphanedSideEffectRecoveryRequired(
            "provider result was not durably bound to the exact attempt; "
            f"attempt {attempt.attempt_id} requires reconciliation and must not be retried"
        ) from exc


def _provider_result_disposition(receipt: VerifiedExternalEffectReceipt) -> str:
    if receipt.provider_outcome == "SUCCESS":
        return "SUCCESS"
    if (
        receipt.provider == "GITHUB"
        and receipt.action_kind == "CREATE_ISSUE_COMMENT"
        and receipt.provider_status in _GITHUB_DEFINITIVE_NO_EFFECT_STATUSES
    ):
        return "DEFINITIVE_FAILURE"
    return "AMBIGUOUS"


def _recovery_required(
    *,
    reason: str,
    attempt: VerifiedExternalEffectAttempt | None,
    system: dict[str, Any] | None = None,
    detail: str | None = None,
    provider_result_disposition: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "system_write": "RECOVERY_REQUIRED",
        "external_effect_state": "POSSIBLY_CREATED",
        "original_success_receipt": "MISSING_OR_INVALID",
        "system_completion": False,
        "automatic_retry_allowed": False,
        "terminal_pass": False,
        "recovery_status": reason,
        "invariant": "UNKNOWN_POST_WRITE_STATE_IS_NOT_SAFE_TO_RETRY",
    }
    if attempt is not None:
        result["attempt_id"] = attempt.attempt_id
        result["attempt_ref"] = attempt.attempt_ref
    if system is not None:
        result["system_receipt_assessment"] = system
    if detail is not None:
        result["detail"] = detail
    if provider_result_disposition is not None:
        result["provider_result_disposition"] = provider_result_disposition
    return result


def assess_orphaned_side_effect_recovery(
    *,
    attempt: VerifiedExternalEffectAttempt,
    system_receipt: VerifiedAttemptBoundReceipt | None,
    recovery_scan: VerifiedExternalRecoveryScan | None,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
    expected_effect_sha256: str,
) -> dict[str, Any]:
    """Apply FAI-009 fail-closed recovery semantics without retrying the mutation."""
    try:
        verified_attempt = validate_external_effect_attempt(
            attempt,
            expected_provider=expected_provider,
            expected_action_kind=expected_action_kind,
            expected_target=expected_target,
            expected_effect_sha256=expected_effect_sha256,
        )
    except ExternalEffectReceiptError as exc:
        return _recovery_required(
            reason="ATTEMPT_EVIDENCE_INVALID",
            attempt=attempt if isinstance(attempt, VerifiedExternalEffectAttempt) else None,
            detail=str(exc),
        )

    receipt: VerifiedExternalEffectReceipt | None = None
    if system_receipt is None:
        system = assess_system_write(
            receipt=None,
            expected_provider=expected_provider,
            expected_action_kind=expected_action_kind,
            expected_target=expected_target,
            expected_effect_sha256=expected_effect_sha256,
        )
    else:
        try:
            receipt = validate_attempt_bound_receipt(
                system_receipt,
                attempt=verified_attempt,
            )
        except ExternalEffectReceiptError as exc:
            return _recovery_required(
                reason="SYSTEM_RECEIPT_NOT_BOUND_TO_ATTEMPT",
                attempt=verified_attempt,
                detail=str(exc),
            )
        system = assess_system_write(
            receipt=receipt,
            expected_provider=expected_provider,
            expected_action_kind=expected_action_kind,
            expected_target=expected_target,
            expected_effect_sha256=expected_effect_sha256,
        )

    if receipt is not None:
        disposition = _provider_result_disposition(receipt)
        if disposition == "SUCCESS" and system["system_write"] == "COMPLETED":
            return {
                "system": system,
                "system_write": "COMPLETED",
                "external_effect_state": "CREATED_WITH_DURABLE_RECEIPT",
                "orphaned_side_effect": "NOT_ACTIVE",
                "recovery_status": "NOT_REQUIRED_AUTHORITATIVE_RECEIPT_PRESENT",
                "provider_result_disposition": disposition,
                "system_completion": True,
                "automatic_retry_allowed": False,
                "terminal_pass": False,
                "attempt_id": verified_attempt.attempt_id,
                "receipt_binding_ref": system_receipt.binding_ref,
            }
        if disposition == "DEFINITIVE_FAILURE" and system["system_write"] == "FAILED":
            return {
                "system": system,
                "system_write": "FAILED",
                "external_effect_state": "AUTHORITATIVE_PROVIDER_FAILURE",
                "orphaned_side_effect": "NOT_ACTIVE",
                "recovery_status": "NOT_REQUIRED_DEFINITIVE_FAILURE_PRESENT",
                "provider_result_disposition": disposition,
                "system_completion": False,
                "automatic_retry_allowed": False,
                "terminal_pass": False,
                "attempt_id": verified_attempt.attempt_id,
                "receipt_binding_ref": system_receipt.binding_ref,
            }
        if disposition == "AMBIGUOUS":
            arp_system_write = system.get("system_write")
            system = dict(system)
            system["arp_system_write"] = arp_system_write
            system["system_write"] = "AMBIGUOUS_PROVIDER_RESULT"
            system["system_completion"] = False
            system["ose_provider_result_disposition"] = disposition
            if recovery_scan is None:
                return _recovery_required(
                    reason="AMBIGUOUS_PROVIDER_RESULT",
                    attempt=verified_attempt,
                    system=system,
                    provider_result_disposition=disposition,
                )

    if recovery_scan is None:
        return _recovery_required(
            reason="AUTHORITATIVE_PROVIDER_RECONCILIATION_REQUIRED",
            attempt=verified_attempt,
            system=system,
        )

    try:
        verified_scan = validate_external_recovery_scan(
            recovery_scan,
            expected_provider=expected_provider,
            expected_action_kind=expected_action_kind,
            expected_target=expected_target,
        )
        if _record_root(verified_scan.scan_ref) != _attempt_root(verified_attempt):
            raise ExternalEffectReceiptError(
                "recovery scan is not stored in the attempt evidence root"
            )
        if _utc_datetime(verified_scan.scanned_at, field="scanned_at") < _utc_datetime(
            verified_attempt.started_at, field="started_at"
        ):
            raise ExternalEffectReceiptError("recovery scan predates the write attempt")
    except ExternalEffectReceiptError as exc:
        return _recovery_required(
            reason="RECOVERY_SCAN_INVALID",
            attempt=verified_attempt,
            system=system,
            detail=str(exc),
        )

    if not verified_scan.complete:
        return _recovery_required(
            reason="RECOVERY_SCAN_INCOMPLETE",
            attempt=verified_attempt,
            system=system,
        )

    correlated = [
        candidate
        for candidate in verified_scan.candidates
        if candidate.correlation_id == verified_attempt.attempt_id
    ]
    if len(correlated) == 0:
        return _recovery_required(
            reason="NO_EXACT_CORRELATED_OBJECT_OBSERVED",
            attempt=verified_attempt,
            system=system,
        )
    if len(correlated) != 1:
        return _recovery_required(
            reason="AMBIGUOUS_CORRELATED_OBJECTS",
            attempt=verified_attempt,
            system=system,
        )

    recovered = correlated[0]
    if _utc_datetime(recovered.created_at, field="created_at") < _utc_datetime(
        verified_attempt.started_at, field="started_at"
    ):
        return _recovery_required(
            reason="CORRELATED_OBJECT_PREEXISTS_ATTEMPT",
            attempt=verified_attempt,
            system=system,
        )
    if recovered.effect_sha256 != verified_attempt.effect_sha256:
        return _recovery_required(
            reason="NO_EXACT_CORRELATED_OBJECT_OBSERVED",
            attempt=verified_attempt,
            system=system,
        )

    return {
        "system_write": "RECOVERED_EXTERNAL_EFFECT",
        "external_effect_state": "CREATED_OBJECT_IDENTITY_RECOVERED",
        "original_success_receipt": "MISSING_OR_INVALID",
        "system_completion": False,
        "automatic_retry_allowed": False,
        "terminal_pass": False,
        "recovery_status": "EXACT_PROVIDER_OBJECT_RECOVERED",
        "attempt_id": verified_attempt.attempt_id,
        "object_id": recovered.object_id,
        "object_url": recovered.object_url,
        "created_at": recovered.created_at,
        "effect_sha256": recovered.effect_sha256,
        "recovery_scan_ref": verified_scan.scan_ref,
        "provenance_rule": "RECOVERY_DOES_NOT_FABRICATE_ORIGINAL_SUCCESS_RECEIPT",
        "next_gate": "SEPARATE_INDEPENDENT_EFFECT_VERIFICATION_REQUIRED",
    }
