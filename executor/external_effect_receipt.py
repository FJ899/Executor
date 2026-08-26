from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ExternalEffectReceiptError(ValueError):
    pass


_SCHEMA_VERSION = "executor-external-effect-receipt/2.0"
_EVIDENCE_SCHEMA_VERSION = "executor-external-effect-evidence/1.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_GITHUB_REPOSITORY = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)$"
)
_GITHUB_COMMENT_TARGET = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<issue>[1-9][0-9]*)$"
)
_GITHUB_REF_TARGET = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)@(?P<ref>refs/heads/[A-Za-z0-9._/-]+)$"
)
_GITHUB_COMMENT_FRAGMENT = re.compile(r"^issuecomment-(?P<id>[1-9][0-9]*)$")
_VERIFIED_RECEIPT_PROOF = object()
_VERIFIED_OBSERVATION_PROOF = object()


__all__ = [
    "ExternalEffectReceiptError",
    "VerifiedExternalEffectReceipt",
    "VerifiedExternalObservation",
    "assess_system_write",
    "assess_actor_receipt_provenance",
]


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


def _required_bytes(value: object, *, field: str) -> bytes:
    if not isinstance(value, bytes):
        raise ExternalEffectReceiptError(f"{field} must be bytes")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _validate_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ExternalEffectReceiptError(f"{field} must be a lowercase SHA-256")
    return value


def _parse_utc(value: object, *, field: str) -> str:
    text = _required_text(value, field=field)
    if not text.endswith("Z"):
        raise ExternalEffectReceiptError(f"{field} must be an RFC3339 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise ExternalEffectReceiptError(f"{field} is not a valid timestamp") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ExternalEffectReceiptError(f"{field} must be UTC")
    return text


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ExternalEffectReceiptError(
            f"external effect evidence is not canonical JSON: {exc}"
        ) from exc
    return (text + "\n").encode("utf-8")


def _validate_expected_identity(
    *,
    provider: str,
    action_kind: str,
    target: str,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
) -> None:
    if provider != expected_provider:
        raise ExternalEffectReceiptError("provider mismatch")
    if action_kind != expected_action_kind:
        raise ExternalEffectReceiptError("action_kind mismatch")
    if target != expected_target:
        raise ExternalEffectReceiptError("target mismatch")


def _validate_ref_name(value: str) -> None:
    if (
        not value.startswith("refs/heads/")
        or value.endswith("/")
        or "//" in value
        or ".." in value
        or "@{" in value
        or value.endswith(".")
        or any(ch in value for ch in " ~^:?*[\\")
    ):
        raise ExternalEffectReceiptError("GitHub ref target is not a safe branch ref")


def _validate_provider_target(
    *,
    provider: str,
    action_kind: str,
    target: str,
) -> re.Match[str]:
    if provider != "GITHUB":
        raise ExternalEffectReceiptError(
            "provider/target binding is not implemented for this provider"
        )
    if action_kind == "CREATE_ISSUE_COMMENT":
        target_match = _GITHUB_COMMENT_TARGET.fullmatch(target)
        if target_match is None:
            raise ExternalEffectReceiptError(
                "GitHub issue-comment target must use owner/repo#issue form"
            )
        return target_match
    if action_kind in {"CREATE_ISSUE", "CREATE_PULL_REQUEST"}:
        target_match = _GITHUB_REPOSITORY.fullmatch(target)
        if target_match is None:
            raise ExternalEffectReceiptError(
                "GitHub repository write target must use owner/repo form"
            )
        return target_match
    if action_kind in {"CREATE_GIT_REF", "UPDATE_GIT_REF"}:
        target_match = _GITHUB_REF_TARGET.fullmatch(target)
        if target_match is None:
            raise ExternalEffectReceiptError(
                "GitHub ref target must use owner/repo@refs/heads/<branch> form"
            )
        _validate_ref_name(target_match.group("ref"))
        return target_match
    raise ExternalEffectReceiptError(
        "provider/target binding is not implemented for this write kind"
    )


def _validate_github_url_base(parsed, *, owner: str, repo: str) -> None:
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.params
        or parsed.query
    ):
        raise ExternalEffectReceiptError(
            "GitHub object identity is not bound to the expected target"
        )
    if not parsed.path.startswith(f"/{owner}/{repo}/"):
        raise ExternalEffectReceiptError(
            "GitHub object identity is not bound to the expected target"
        )


def _validate_provider_object_binding(
    *,
    provider: str,
    action_kind: str,
    target: str,
    object_id: str,
    object_url: str,
) -> None:
    target_match = _validate_provider_target(
        provider=provider,
        action_kind=action_kind,
        target=target,
    )
    parsed = urlparse(object_url)
    owner = target_match.group("owner")
    repo = target_match.group("repo")
    _validate_github_url_base(parsed, owner=owner, repo=repo)

    if action_kind == "CREATE_ISSUE_COMMENT":
        if not object_id.isdecimal() or int(object_id) <= 0:
            raise ExternalEffectReceiptError(
                "GitHub issue-comment object_id must be a positive integer string"
            )
        expected_path = f"/{owner}/{repo}/issues/{target_match.group('issue')}"
        fragment_match = _GITHUB_COMMENT_FRAGMENT.fullmatch(parsed.fragment)
        valid = (
            parsed.path == expected_path
            and fragment_match is not None
            and fragment_match.group("id") == object_id
        )
    elif action_kind == "CREATE_ISSUE":
        if not object_id.isdecimal() or int(object_id) <= 0:
            raise ExternalEffectReceiptError(
                "GitHub issue object_id must be a positive integer string"
            )
        valid = parsed.path == f"/{owner}/{repo}/issues/{object_id}" and not parsed.fragment
    elif action_kind == "CREATE_PULL_REQUEST":
        if not object_id.isdecimal() or int(object_id) <= 0:
            raise ExternalEffectReceiptError(
                "GitHub pull-request object_id must be a positive integer string"
            )
        valid = parsed.path == f"/{owner}/{repo}/pull/{object_id}" and not parsed.fragment
    else:
        if _GIT_SHA.fullmatch(object_id) is None:
            raise ExternalEffectReceiptError(
                "GitHub ref receipt object_id must be the resulting commit SHA"
            )
        valid = parsed.path == f"/{owner}/{repo}/commit/{object_id}" and not parsed.fragment

    if not valid:
        raise ExternalEffectReceiptError(
            "GitHub object identity is not bound to the expected target"
        )


def _normalize_system_write(
    *,
    provider: str,
    action_kind: str,
    target: str,
    provider_status: int,
    provider_message: str,
    object_id: str | None,
    object_url: str | None,
    response_sha256: str,
    effect_sha256: str,
) -> dict[str, Any]:
    provider = _required_text(provider, field="provider")
    action_kind = _required_text(action_kind, field="action_kind")
    target = _required_text(target, field="target")
    provider_message = _required_text(provider_message, field="provider_message")
    object_id = _optional_text(object_id, field="object_id")
    object_url = _optional_text(object_url, field="object_url")
    response_sha256 = _validate_sha256(response_sha256, field="response_sha256")
    effect_sha256 = _validate_sha256(effect_sha256, field="effect_sha256")
    _validate_provider_target(
        provider=provider,
        action_kind=action_kind,
        target=target,
    )

    if (
        not isinstance(provider_status, int)
        or isinstance(provider_status, bool)
        or provider_status < 100
        or provider_status > 599
    ):
        raise ExternalEffectReceiptError("provider_status must be an HTTP status integer")

    success = 200 <= provider_status < 300
    if success:
        if object_id is None or object_url is None:
            raise ExternalEffectReceiptError(
                "successful system write requires durable provider object identity"
            )
        _validate_provider_object_binding(
            provider=provider,
            action_kind=action_kind,
            target=target,
            object_id=object_id,
            object_url=object_url,
        )
    elif object_id is not None or object_url is not None:
        raise ExternalEffectReceiptError(
            "failed system write receipt must not claim created object identity"
        )

    return {
        "schema_version": _SCHEMA_VERSION,
        "provider": provider,
        "actor": "SYSTEM",
        "action_kind": action_kind,
        "target": target,
        "provider_status": provider_status,
        "provider_message": provider_message,
        "object_id": object_id,
        "object_url": object_url,
        "response_sha256": response_sha256,
        "effect_sha256": effect_sha256,
        "provider_outcome": "SUCCESS" if success else "FAILURE",
    }


def _ensure_evidence_directory(value: str | Path) -> Path:
    path = Path(value)
    if path.exists() and path.is_symlink():
        raise ExternalEffectReceiptError("evidence_directory must not be a symlink")
    path.mkdir(parents=True, exist_ok=True)
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ExternalEffectReceiptError("evidence_directory must be a directory")
    return resolved


def _read_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ExternalEffectReceiptError(
            f"persisted external effect evidence is unavailable: {path}"
        ) from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ExternalEffectReceiptError(
                "persisted external effect evidence must be one regular file"
            )
        with os.fdopen(fd, "rb", closefd=False) as handle:
            return handle.read()
    finally:
        os.close(fd)


def _persist_evidence(
    *,
    kind: str,
    payload: dict[str, Any],
    provider_response: bytes,
    evidence_directory: str | Path,
) -> tuple[str, str]:
    directory = _ensure_evidence_directory(evidence_directory)
    envelope = {
        "schema_version": _EVIDENCE_SCHEMA_VERSION,
        "kind": kind,
        "payload": payload,
        "provider_response_b64": base64.b64encode(provider_response).decode("ascii"),
    }
    encoded = _canonical_json_bytes(envelope)
    evidence_sha256 = _sha256_bytes(encoded)
    final_path = directory / f"{kind.lower()}-{evidence_sha256}.json"

    if final_path.exists():
        if _read_regular_file(final_path) != encoded:
            raise ExternalEffectReceiptError(
                "content-addressed external effect evidence collision"
            )
    else:
        fd, temporary_name = tempfile.mkstemp(
            prefix=".external-effect-",
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
            directory_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    persisted = _read_regular_file(final_path)
    if _sha256_bytes(persisted) != evidence_sha256 or persisted != encoded:
        raise ExternalEffectReceiptError(
            "persisted external effect evidence failed read-after-write verification"
        )
    return str(final_path), evidence_sha256


@dataclass(frozen=True)
class VerifiedExternalEffectReceipt:
    provider: str
    actor: str
    action_kind: str
    target: str
    provider_status: int
    provider_message: str
    object_id: str | None
    object_url: str | None
    response_sha256: str
    effect_sha256: str
    provider_outcome: str
    receipt_ref: str
    evidence_sha256: str
    _proof: object = field(repr=False, compare=False, init=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _VERIFIED_RECEIPT_PROOF:
            raise ExternalEffectReceiptError(
                "VerifiedExternalEffectReceipt must be minted by the trusted provider gateway"
            )

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "provider": self.provider,
            "actor": self.actor,
            "action_kind": self.action_kind,
            "target": self.target,
            "provider_status": self.provider_status,
            "provider_message": self.provider_message,
            "object_id": self.object_id,
            "object_url": self.object_url,
            "response_sha256": self.response_sha256,
            "effect_sha256": self.effect_sha256,
            "provider_outcome": self.provider_outcome,
        }


@dataclass(frozen=True)
class VerifiedExternalObservation:
    provider: str
    action_kind: str
    target: str
    object_id: str
    object_url: str
    effect_sha256: str
    observed_at: str
    response_sha256: str
    observation_ref: str
    evidence_sha256: str
    _proof: object = field(repr=False, compare=False, init=False, default=None)

    def __post_init__(self) -> None:
        if self._proof is not _VERIFIED_OBSERVATION_PROOF:
            raise ExternalEffectReceiptError(
                "VerifiedExternalObservation must be minted by the trusted verifier gateway"
            )

    def evidence_payload(self) -> dict[str, Any]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "provider": self.provider,
            "actor": "VERIFIER",
            "action_kind": self.action_kind,
            "target": self.target,
            "object_id": self.object_id,
            "object_url": self.object_url,
            "effect_sha256": self.effect_sha256,
            "observed_at": self.observed_at,
            "response_sha256": self.response_sha256,
        }


def _mint_verified_receipt(
    *,
    normalized: dict[str, Any],
    receipt_ref: str,
    evidence_sha256: str,
) -> VerifiedExternalEffectReceipt:
    instance = object.__new__(VerifiedExternalEffectReceipt)
    for key, value in normalized.items():
        object.__setattr__(instance, key, value)
    object.__setattr__(instance, "receipt_ref", receipt_ref)
    object.__setattr__(instance, "evidence_sha256", evidence_sha256)
    object.__setattr__(instance, "_proof", _VERIFIED_RECEIPT_PROOF)
    return instance


def _mint_verified_observation(
    *,
    payload: dict[str, Any],
    observation_ref: str,
    evidence_sha256: str,
) -> VerifiedExternalObservation:
    instance = object.__new__(VerifiedExternalObservation)
    for key in (
        "provider",
        "action_kind",
        "target",
        "object_id",
        "object_url",
        "effect_sha256",
        "observed_at",
        "response_sha256",
    ):
        object.__setattr__(instance, key, payload[key])
    object.__setattr__(instance, "observation_ref", observation_ref)
    object.__setattr__(instance, "evidence_sha256", evidence_sha256)
    object.__setattr__(instance, "_proof", _VERIFIED_OBSERVATION_PROOF)
    return instance


def _persist_verified_system_write_receipt(
    *,
    provider_response: bytes,
    effect_bytes: bytes,
    evidence_directory: str | Path,
    provider: str,
    action_kind: str,
    target: str,
    provider_status: int,
    provider_message: str,
    object_id: str | None = None,
    object_url: str | None = None,
) -> VerifiedExternalEffectReceipt:
    """Trusted provider-gateway hook.

    Raw caller dictionaries cannot become authoritative receipts. A provider
    adapter must supply the actual response bytes and attempted effect bytes to
    this private hook after the provider call has returned.
    """
    provider_response = _required_bytes(
        provider_response, field="provider_response"
    )
    effect_bytes = _required_bytes(effect_bytes, field="effect_bytes")
    normalized = _normalize_system_write(
        provider=provider,
        action_kind=action_kind,
        target=target,
        provider_status=provider_status,
        provider_message=provider_message,
        object_id=object_id,
        object_url=object_url,
        response_sha256=_sha256_bytes(provider_response),
        effect_sha256=_sha256_bytes(effect_bytes),
    )
    receipt_ref, evidence_sha256 = _persist_evidence(
        kind="SYSTEM_WRITE_RECEIPT",
        payload=normalized,
        provider_response=provider_response,
        evidence_directory=evidence_directory,
    )
    return _mint_verified_receipt(
        normalized=normalized,
        receipt_ref=receipt_ref,
        evidence_sha256=evidence_sha256,
    )


def _persist_verified_external_observation(
    *,
    provider_response: bytes,
    observed_effect_bytes: bytes,
    evidence_directory: str | Path,
    provider: str,
    action_kind: str,
    target: str,
    object_id: str,
    object_url: str,
    observed_at: str,
) -> VerifiedExternalObservation:
    """Trusted verifier-gateway hook for an independently read provider object."""
    provider_response = _required_bytes(
        provider_response, field="provider_response"
    )
    observed_effect_bytes = _required_bytes(
        observed_effect_bytes, field="observed_effect_bytes"
    )
    provider = _required_text(provider, field="provider")
    action_kind = _required_text(action_kind, field="action_kind")
    target = _required_text(target, field="target")
    object_id = _required_text(object_id, field="object_id")
    object_url = _required_text(object_url, field="object_url")
    observed_at = _parse_utc(observed_at, field="observed_at")

    _validate_provider_object_binding(
        provider=provider,
        action_kind=action_kind,
        target=target,
        object_id=object_id,
        object_url=object_url,
    )

    payload = {
        "schema_version": _SCHEMA_VERSION,
        "provider": provider,
        "actor": "VERIFIER",
        "action_kind": action_kind,
        "target": target,
        "object_id": object_id,
        "object_url": object_url,
        "effect_sha256": _sha256_bytes(observed_effect_bytes),
        "observed_at": observed_at,
        "response_sha256": _sha256_bytes(provider_response),
    }
    observation_ref, evidence_sha256 = _persist_evidence(
        kind="INDEPENDENT_OBSERVATION",
        payload=payload,
        provider_response=provider_response,
        evidence_directory=evidence_directory,
    )
    return _mint_verified_observation(
        payload=payload,
        observation_ref=observation_ref,
        evidence_sha256=evidence_sha256,
    )


def _verify_persisted_evidence(
    *,
    kind: str,
    payload: dict[str, Any],
    evidence_ref: str,
    evidence_sha256: str,
) -> None:
    evidence_sha256 = _validate_sha256(
        evidence_sha256, field="evidence_sha256"
    )
    path = Path(_required_text(evidence_ref, field="evidence_ref"))
    encoded = _read_regular_file(path)
    if _sha256_bytes(encoded) != evidence_sha256:
        raise ExternalEffectReceiptError(
            "persisted external effect evidence hash mismatch"
        )
    try:
        envelope = json.loads(encoded.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalEffectReceiptError(
            "persisted external effect evidence is not valid JSON"
        ) from exc
    if (
        not isinstance(envelope, dict)
        or envelope.get("schema_version") != _EVIDENCE_SCHEMA_VERSION
        or envelope.get("kind") != kind
        or envelope.get("payload") != payload
    ):
        raise ExternalEffectReceiptError(
            "persisted external effect evidence does not bind the verified object"
        )
    raw_b64 = envelope.get("provider_response_b64")
    if not isinstance(raw_b64, str):
        raise ExternalEffectReceiptError(
            "persisted external effect evidence is missing provider response bytes"
        )
    try:
        provider_response = base64.b64decode(raw_b64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ExternalEffectReceiptError(
            "persisted provider response encoding is invalid"
        ) from exc
    if _sha256_bytes(provider_response) != payload["response_sha256"]:
        raise ExternalEffectReceiptError(
            "provider response SHA-256 is not bound to persisted response bytes"
        )


def validate_verified_system_write_receipt(
    receipt: VerifiedExternalEffectReceipt,
    *,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
    expected_effect_sha256: str,
) -> VerifiedExternalEffectReceipt:
    if not isinstance(receipt, VerifiedExternalEffectReceipt):
        raise ExternalEffectReceiptError(
            "system write assessment requires a VerifiedExternalEffectReceipt"
        )
    _validate_expected_identity(
        provider=receipt.provider,
        action_kind=receipt.action_kind,
        target=receipt.target,
        expected_provider=expected_provider,
        expected_action_kind=expected_action_kind,
        expected_target=expected_target,
    )
    if receipt.actor != "SYSTEM":
        raise ExternalEffectReceiptError("verified system receipt actor mismatch")
    if receipt.effect_sha256 != _validate_sha256(
        expected_effect_sha256, field="expected_effect_sha256"
    ):
        raise ExternalEffectReceiptError(
            "verified system receipt effect fingerprint mismatch"
        )

    normalized = _normalize_system_write(
        provider=receipt.provider,
        action_kind=receipt.action_kind,
        target=receipt.target,
        provider_status=receipt.provider_status,
        provider_message=receipt.provider_message,
        object_id=receipt.object_id,
        object_url=receipt.object_url,
        response_sha256=receipt.response_sha256,
        effect_sha256=receipt.effect_sha256,
    )
    if normalized["provider_outcome"] != receipt.provider_outcome:
        raise ExternalEffectReceiptError("verified system receipt outcome mismatch")

    _verify_persisted_evidence(
        kind="SYSTEM_WRITE_RECEIPT",
        payload=receipt.evidence_payload(),
        evidence_ref=receipt.receipt_ref,
        evidence_sha256=receipt.evidence_sha256,
    )
    return receipt


def validate_verified_external_observation(
    observation: VerifiedExternalObservation,
    *,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
    expected_effect_sha256: str,
) -> VerifiedExternalObservation:
    if not isinstance(observation, VerifiedExternalObservation):
        raise ExternalEffectReceiptError(
            "independent verification requires a VerifiedExternalObservation"
        )
    _validate_expected_identity(
        provider=observation.provider,
        action_kind=observation.action_kind,
        target=observation.target,
        expected_provider=expected_provider,
        expected_action_kind=expected_action_kind,
        expected_target=expected_target,
    )
    if observation.effect_sha256 != _validate_sha256(
        expected_effect_sha256, field="expected_effect_sha256"
    ):
        raise ExternalEffectReceiptError(
            "independent observation effect fingerprint mismatch"
        )
    _validate_provider_object_binding(
        provider=observation.provider,
        action_kind=observation.action_kind,
        target=observation.target,
        object_id=observation.object_id,
        object_url=observation.object_url,
    )
    _parse_utc(observation.observed_at, field="observed_at")
    _validate_sha256(observation.response_sha256, field="response_sha256")
    _verify_persisted_evidence(
        kind="INDEPENDENT_OBSERVATION",
        payload=observation.evidence_payload(),
        evidence_ref=observation.observation_ref,
        evidence_sha256=observation.evidence_sha256,
    )
    return observation


def assess_system_write(
    *,
    receipt: VerifiedExternalEffectReceipt | None,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
    expected_effect_sha256: str,
) -> dict[str, Any]:
    """Apply INV-AR1 to a system-performed mutating action."""
    if receipt is None:
        return {
            "system_write": "UNVERIFIED",
            "system_receipt": "MISSING",
            "system_completion": False,
            "terminal_pass": False,
            "reason": "NO_RECEIPT_NO_SYSTEM_COMPLETION_CLAIM",
        }

    try:
        verified = validate_verified_system_write_receipt(
            receipt,
            expected_provider=expected_provider,
            expected_action_kind=expected_action_kind,
            expected_target=expected_target,
            expected_effect_sha256=expected_effect_sha256,
        )
    except ExternalEffectReceiptError as exc:
        return {
            "system_write": "UNVERIFIED",
            "system_receipt": "INVALID",
            "system_completion": False,
            "terminal_pass": False,
            "reason": "INVALID_AUTHORITATIVE_SYSTEM_RECEIPT",
            "detail": str(exc),
        }

    if verified.provider_outcome == "FAILURE":
        return {
            "system_write": "FAILED",
            "system_receipt": "AUTHORITATIVE_FAILURE_RECEIPT",
            "system_completion": False,
            "terminal_pass": False,
            "receipt": verified,
        }

    return {
        "system_write": "COMPLETED",
        "system_receipt": "AUTHORITATIVE_SUCCESS_RECEIPT",
        "system_completion": True,
        "terminal_pass": False,
        "verification": "INDEPENDENT_READ_REQUIRED",
        "receipt": verified,
    }


def assess_actor_receipt_provenance(
    *,
    system_receipt: VerifiedExternalEffectReceipt | None,
    human_write_claim: bool,
    independent_observation: VerifiedExternalObservation | None,
    expected_provider: str,
    expected_action_kind: str,
    expected_target: str,
    expected_effect_sha256: str,
) -> dict[str, Any]:
    """Apply INV-AR1..AR3 across SYSTEM and HUMAN provenance boundaries."""
    if type(human_write_claim) is not bool:
        raise ExternalEffectReceiptError("human_write_claim must be a boolean")
    if independent_observation is not None and not isinstance(
        independent_observation, VerifiedExternalObservation
    ):
        raise ExternalEffectReceiptError(
            "independent_observation must be null or VerifiedExternalObservation"
        )

    system = assess_system_write(
        receipt=system_receipt,
        expected_provider=expected_provider,
        expected_action_kind=expected_action_kind,
        expected_target=expected_target,
        expected_effect_sha256=expected_effect_sha256,
    )

    if not human_write_claim:
        return {
            "system": system,
            "human_write": "NOT_REPORTED",
            "current_result": system["system_write"],
            "terminal_pass": False,
        }

    if independent_observation is None:
        human_state = "UNVERIFIED"
        observation_status = "MISSING"
        observation_detail = None
    else:
        try:
            validate_verified_external_observation(
                independent_observation,
                expected_provider=expected_provider,
                expected_action_kind=expected_action_kind,
                expected_target=expected_target,
                expected_effect_sha256=expected_effect_sha256,
            )
        except ExternalEffectReceiptError as exc:
            human_state = "UNVERIFIED"
            observation_status = "INVALID"
            observation_detail = str(exc)
        else:
            human_state = "OBSERVED"
            observation_status = "VERIFIED"
            observation_detail = None

    result = {
        "system": system,
        "human_write": "HUMAN_REPORTED",
        "human_verification": human_state,
        "current_result": f"HUMAN_REPORTED / {human_state}",
        "terminal_pass": False,
        "provenance_rule": "HUMAN_CLAIM_MUST_NOT_INHERIT_SYSTEM_COMPLETION",
        "evidence_non_substitution": True,
        "observation_status": observation_status,
    }
    if observation_detail is not None:
        result["observation_detail"] = observation_detail
    return result
