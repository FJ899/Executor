from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from executor.external_effect_receipt import (
    ExternalEffectReceiptError,
    VerifiedExternalObservation,
    _persist_evidence,
    _persist_verified_external_observation,
    _sha256_bytes,
    _validate_provider_target,
    validate_verified_external_observation,
)
from executor.github_authority import GovernedAuthorityLedger
from executor.orphaned_side_effect import (
    OrphanedSideEffectRecoveryRequired,
    VerifiedAttemptBoundReceipt,
    VerifiedExternalEffectAttempt,
    _persist_external_effect_attempt,
    _persist_provider_result_for_attempt,
    assess_orphaned_side_effect_recovery,
)


SUPPORTED_EFFECTS = frozenset(
    {
        "CREATE_ISSUE",
        "CREATE_GIT_REF",
        "UPDATE_GIT_REF",
        "CREATE_PULL_REQUEST",
    }
)


class GitHubEffectError(RuntimeError):
    pass


class GitHubEffectRecoveryRequired(GitHubEffectError):
    pass


@dataclass(frozen=True)
class ProviderWriteResult:
    provider_status: int
    provider_message: str
    raw_response: bytes
    object_id: str | None = None
    object_url: str | None = None


@dataclass(frozen=True)
class ProviderReadResult:
    complete: bool
    exists: bool
    raw_response: bytes
    observed_effect_bytes: bytes | None = None
    object_id: str | None = None
    object_url: str | None = None


class GitHubEffectGateway(Protocol):
    """Provider-specific EFFECT/OBSERVE boundary.

    Implementations must perform only the exact action/target supplied by the
    transaction. They must not retry writes internally. Read-back must be a
    fresh provider observation and set ``complete`` false if pagination,
    timeout, 5xx, or any other uncertainty prevents an authoritative answer.
    """

    def write(
        self,
        *,
        action_kind: str,
        target: str,
        effect_bytes: bytes,
        correlation_id: str,
    ) -> ProviderWriteResult:
        ...

    def observe(
        self,
        *,
        action_kind: str,
        target: str,
        effect_sha256: str,
        correlation_id: str,
    ) -> ProviderReadResult:
        ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_effect_bytes(payload: dict[str, Any]) -> bytes:
    try:
        text = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise GitHubEffectError(f"effect payload is not canonical JSON: {exc}") from exc
    return (text + "\n").encode("utf-8")


def verify_effect_intent(*, action_kind: str, target: str, effect_bytes: bytes) -> str:
    if action_kind not in SUPPORTED_EFFECTS:
        raise GitHubEffectError(f"unsupported consequential GitHub effect: {action_kind}")
    if not isinstance(effect_bytes, bytes) or not effect_bytes:
        raise GitHubEffectError("effect_bytes must be non-empty bytes")
    try:
        _validate_provider_target(provider="GITHUB", action_kind=action_kind, target=target)
    except ExternalEffectReceiptError as exc:
        raise GitHubEffectError(str(exc)) from exc
    return hashlib.sha256(effect_bytes).hexdigest()


def _persist_absence_observation(
    *,
    attempt: VerifiedExternalEffectAttempt,
    read: ProviderReadResult,
    evidence_directory: Path,
) -> dict[str, Any]:
    if not read.complete or read.exists:
        raise GitHubEffectError("absence observation must be complete and absent")
    payload = {
        "schema_version": "executor-external-effect-absence/1.0",
        "provider": attempt.provider,
        "actor": "RECOVERY_VERIFIER",
        "action_kind": attempt.action_kind,
        "target": attempt.target,
        "attempt_id": attempt.attempt_id,
        "effect_sha256": attempt.effect_sha256,
        "observed_at": _utc_now(),
        "complete": True,
        "exists": False,
        "response_sha256": _sha256_bytes(read.raw_response),
    }
    ref, evidence_sha256 = _persist_evidence(
        kind="INDEPENDENT_ABSENCE_OBSERVATION",
        payload=payload,
        provider_response=read.raw_response,
        evidence_directory=evidence_directory,
    )
    return {**payload, "observation_ref": ref, "evidence_sha256": evidence_sha256}


def _persist_positive_observation(
    *,
    attempt: VerifiedExternalEffectAttempt,
    read: ProviderReadResult,
    evidence_directory: Path,
) -> VerifiedExternalObservation:
    if (
        not read.complete
        or not read.exists
        or read.observed_effect_bytes is None
        or read.object_id is None
        or read.object_url is None
    ):
        raise GitHubEffectError("positive observation is incomplete")
    observation = _persist_verified_external_observation(
        provider_response=read.raw_response,
        observed_effect_bytes=read.observed_effect_bytes,
        evidence_directory=evidence_directory,
        provider=attempt.provider,
        action_kind=attempt.action_kind,
        target=attempt.target,
        object_id=read.object_id,
        object_url=read.object_url,
        observed_at=_utc_now(),
    )
    validate_verified_external_observation(
        observation,
        expected_provider=attempt.provider,
        expected_action_kind=attempt.action_kind,
        expected_target=attempt.target,
        expected_effect_sha256=attempt.effect_sha256,
    )
    return observation


@dataclass
class GitHubEffectTransaction:
    run_id: str
    authority_key: str
    action_kind: str
    target: str
    effect_bytes: bytes
    not_after: str
    evidence_directory: Path
    ledger: GovernedAuthorityLedger

    def __post_init__(self) -> None:
        self.effect_sha256 = verify_effect_intent(
            action_kind=self.action_kind,
            target=self.target,
            effect_bytes=self.effect_bytes,
        )
        self.consumption = None
        self.attempt: VerifiedExternalEffectAttempt | None = None
        self.bound_receipt: VerifiedAttemptBoundReceipt | None = None

    def reserve_and_consume(self) -> VerifiedExternalEffectAttempt:
        if self.attempt is not None:
            raise GitHubEffectError("effect transaction is already reserved")
        self.consumption = self.ledger.consume(
            authority_key=self.authority_key,
            payload_sha256=self.effect_sha256,
            action_kind=self.action_kind,
            run_id=self.run_id,
            not_after=self.not_after,
        )
        try:
            self.attempt = _persist_external_effect_attempt(
                provider="GITHUB",
                action_kind=self.action_kind,
                target=self.target,
                effect_bytes=self.effect_bytes,
                started_at=_utc_now(),
                evidence_directory=self.evidence_directory,
            )
        except Exception as exc:
            raise GitHubEffectRecoveryRequired(
                "authority was consumed but pre-write effect journal could not be verified; no write may be attempted"
            ) from exc
        return self.attempt

    def effect(self, gateway: GitHubEffectGateway) -> ProviderWriteResult | None:
        if self.attempt is None or self.consumption is None:
            raise GitHubEffectError("reserve_and_consume must complete before EFFECT")
        try:
            result = gateway.write(
                action_kind=self.action_kind,
                target=self.target,
                effect_bytes=self.effect_bytes,
                correlation_id=self.attempt.attempt_id,
            )
        except Exception:
            # The request may have crossed the provider boundary. Never retry here.
            return None
        try:
            self.bound_receipt = _persist_provider_result_for_attempt(
                attempt=self.attempt,
                provider_response=result.raw_response,
                effect_bytes=self.effect_bytes,
                evidence_directory=self.evidence_directory,
                provider_status=result.provider_status,
                provider_message=result.provider_message,
                object_id=result.object_id,
                object_url=result.object_url,
            )
        except OrphanedSideEffectRecoveryRequired:
            self.bound_receipt = None
        return result

    def observe_and_bind(self, gateway: GitHubEffectGateway) -> dict[str, Any]:
        if self.attempt is None or self.consumption is None:
            raise GitHubEffectError("effect transaction was not reserved")

        # First preserve the legacy OSE assessment. For a durable success receipt
        # this proves the write is bound to the exact pre-write attempt. Any
        # missing/ambiguous result remains recovery-required until fresh read-back.
        ose = assess_orphaned_side_effect_recovery(
            attempt=self.attempt,
            system_receipt=self.bound_receipt,
            recovery_scan=None,
            expected_provider="GITHUB",
            expected_action_kind=self.action_kind,
            expected_target=self.target,
            expected_effect_sha256=self.effect_sha256,
        )

        try:
            read = gateway.observe(
                action_kind=self.action_kind,
                target=self.target,
                effect_sha256=self.effect_sha256,
                correlation_id=self.attempt.attempt_id,
            )
        except Exception as exc:
            return {
                "status": "RECOVERY_REQUIRED",
                "reason": "OBSERVATION_FAILED",
                "detail": str(exc),
                "attempt_id": self.attempt.attempt_id,
                "automatic_retry_allowed": False,
                "ose": ose,
            }

        if not read.complete:
            return {
                "status": "RECOVERY_REQUIRED",
                "reason": "OBSERVATION_INCOMPLETE",
                "attempt_id": self.attempt.attempt_id,
                "automatic_retry_allowed": False,
                "ose": ose,
            }

        if read.exists:
            try:
                observation = _persist_positive_observation(
                    attempt=self.attempt,
                    read=read,
                    evidence_directory=self.evidence_directory,
                )
            except (GitHubEffectError, ExternalEffectReceiptError) as exc:
                return {
                    "status": "RECOVERY_REQUIRED",
                    "reason": "OBSERVED_OBJECT_DOES_NOT_MATCH_EFFECT",
                    "detail": str(exc),
                    "attempt_id": self.attempt.attempt_id,
                    "automatic_retry_allowed": False,
                    "ose": ose,
                }
            result = {
                "schema_version": "executor-github-effect-result/1.0",
                "status": (
                    "EFFECT_COMPLETED_AND_OBSERVED"
                    if ose.get("system_completion") is True
                    else "RECOVERED_EXTERNAL_EFFECT"
                ),
                "provider": "GITHUB",
                "action_kind": self.action_kind,
                "target": self.target,
                "effect_sha256": self.effect_sha256,
                "attempt_id": self.attempt.attempt_id,
                "object_id": observation.object_id,
                "object_url": observation.object_url,
                "observation_ref": observation.observation_ref,
                "automatic_retry_allowed": False,
                "original_success_receipt": (
                    "PRESENT" if ose.get("system_completion") is True else "MISSING_OR_INVALID"
                ),
            }
        else:
            absence = _persist_absence_observation(
                attempt=self.attempt,
                read=read,
                evidence_directory=self.evidence_directory,
            )
            result = {
                "schema_version": "executor-github-effect-result/1.0",
                "status": "NO_EFFECT_CONFIRMED",
                "provider": "GITHUB",
                "action_kind": self.action_kind,
                "target": self.target,
                "effect_sha256": self.effect_sha256,
                "attempt_id": self.attempt.attempt_id,
                "absence_observation": absence,
                "automatic_retry_allowed": False,
                "next_attempt_requires_new_authority": True,
            }

        result["authority_result_binding"] = self.ledger.bind_result(
            consumption=self.consumption,
            result=result,
        )
        return result

    def execute(self, gateway: GitHubEffectGateway) -> dict[str, Any]:
        """VERIFY -> RESERVE -> CONSUME -> EFFECT -> OBSERVE -> BIND RESULT."""
        self.reserve_and_consume()
        self.effect(gateway)
        return self.observe_and_bind(gateway)
