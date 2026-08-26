from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from executor.external_effect_receipt import (
    ExternalEffectReceiptError,
    _read_regular_file,
    _sha256_bytes,
)
from executor.github_authority import (
    GlobalAuthorityReservation,
    GovernedAuthorityConsumption,
    GovernedAuthorityLedger,
    ResultBindingRecoveryRequired,
)
from executor.github_effect_transaction import (
    GitHubEffectGateway,
    GitHubEffectTransaction,
    verify_effect_intent,
)
from executor.orphaned_side_effect import (
    VerifiedExternalEffectAttempt,
    _mint_attempt,
    validate_external_effect_attempt,
)


class GitHubEffectRestartRecoveryError(RuntimeError):
    pass


class PayloadBindingGateway(GitHubEffectGateway, Protocol):
    def bind_effect_payload(self, payload: dict[str, Any]) -> None:
        ...


def _load_attempts(
    *,
    evidence_directory: Path,
    provider: str,
    action_kind: str,
    target: str,
    effect_sha256: str,
) -> list[VerifiedExternalEffectAttempt]:
    matches: list[VerifiedExternalEffectAttempt] = []
    for path in sorted(evidence_directory.glob("external_effect_attempt-ose-*.json")):
        try:
            raw = _read_regular_file(path)
            envelope = json.loads(raw.decode("utf-8"))
        except (ExternalEffectReceiptError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(envelope, dict) or envelope.get("kind") != "EXTERNAL_EFFECT_ATTEMPT":
            continue
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("provider") != provider
            or payload.get("action_kind") != action_kind
            or payload.get("target") != target
            or payload.get("effect_sha256") != effect_sha256
        ):
            continue
        attempt = _mint_attempt(
            payload=payload,
            attempt_ref=str(path),
            evidence_sha256=_sha256_bytes(raw),
        )
        validate_external_effect_attempt(
            attempt,
            expected_provider=provider,
            expected_action_kind=action_kind,
            expected_target=target,
            expected_effect_sha256=effect_sha256,
        )
        matches.append(attempt)
    return matches


def _recover_consumption(
    *,
    ledger: GovernedAuthorityLedger,
    authority_key: str,
    payload_sha256: str,
    action_kind: str,
    run_id: str,
) -> GovernedAuthorityConsumption:
    local_matches = [
        item
        for item in ledger.unresolved()
        if item.authority_key == authority_key
        and item.payload_sha256 == payload_sha256
        and item.action_kind == action_kind
        and item.run_id == run_id
    ]
    if len(local_matches) != 1:
        raise GitHubEffectRestartRecoveryError(
            "restart recovery requires exactly one matching unresolved local authority consumption"
        )
    ref = ledger.global_authority._ref_for(authority_key)
    current = ledger.global_authority._get_ref(ref)
    if current is None:
        raise GitHubEffectRestartRecoveryError("global authority reservation is missing")
    obj = current.get("object")
    sha = obj.get("sha") if isinstance(obj, dict) else None
    if not isinstance(sha, str):
        raise GitHubEffectRestartRecoveryError("global authority ref has no commit identity")
    receipt = ledger.global_authority._parse_receipt(
        ledger.global_authority._get_commit(sha)
    )
    for field, expected in {
        "authority_key": authority_key,
        "payload_sha256": payload_sha256,
        "action_kind": action_kind,
        "run_id": run_id,
    }.items():
        if receipt.get(field) != expected:
            raise GitHubEffectRestartRecoveryError(
                f"global authority recovery {field} differs from local consumption"
            )
    if receipt.get("state") not in {"RESERVED", "GLOBAL_RESULT_BOUND", "FINAL"}:
        raise GitHubEffectRestartRecoveryError("global authority recovery state is invalid")
    reservation = GlobalAuthorityReservation(
        authority_key=authority_key,
        payload_sha256=payload_sha256,
        action_kind=action_kind,
        run_id=run_id,
        ref=ref,
        reservation_sha=sha,
        not_after=receipt.get("not_after"),
        provider_created_at=None,
    )
    return GovernedAuthorityConsumption(
        local=local_matches[0],
        global_reservation=reservation,
    )


def recover_interrupted_effect(
    *,
    ledger: GovernedAuthorityLedger,
    gateway: PayloadBindingGateway,
    run_id: str,
    authority_key: str,
    action_kind: str,
    target: str,
    effect_payload: dict[str, Any],
    effect_bytes: bytes,
    evidence_directory: str | Path,
    not_after: str,
) -> dict[str, Any]:
    """Restart recovery: OBSERVE first; provider write is never called.

    The caller must reconstruct the exact frozen effect payload. This function
    verifies its fingerprint against both authority and the durable pre-write
    attempt. If exactly one unresolved attempt exists, it reuses that attempt,
    performs only a provider read, and completes result binding when possible.
    """

    effect_sha256 = verify_effect_intent(
        action_kind=action_kind,
        target=target,
        effect_bytes=effect_bytes,
    )
    attempts = _load_attempts(
        evidence_directory=Path(evidence_directory),
        provider="GITHUB",
        action_kind=action_kind,
        target=target,
        effect_sha256=effect_sha256,
    )
    if len(attempts) != 1:
        raise GitHubEffectRestartRecoveryError(
            "restart recovery requires exactly one matching durable pre-write attempt"
        )
    consumption = _recover_consumption(
        ledger=ledger,
        authority_key=authority_key,
        payload_sha256=effect_sha256,
        action_kind=action_kind,
        run_id=run_id,
    )
    gateway.bind_effect_payload(effect_payload)
    transaction = GitHubEffectTransaction(
        run_id=run_id,
        authority_key=authority_key,
        action_kind=action_kind,
        target=target,
        effect_bytes=effect_bytes,
        not_after=not_after,
        evidence_directory=Path(evidence_directory),
        ledger=ledger,
    )
    transaction.consumption = consumption
    transaction.attempt = attempts[0]
    transaction.bound_receipt = None
    try:
        result = transaction.observe_and_bind(gateway)
    except ResultBindingRecoveryRequired as exc:
        return {
            "schema_version": "executor-github-effect-restart-recovery/1.0",
            "status": "GLOBAL_RESULT_BOUND_LOCAL_BINDING_REQUIRED",
            "attempt_id": attempts[0].attempt_id,
            "effect_sha256": effect_sha256,
            "global_binding": exc.global_binding,
            "automatic_retry_allowed": False,
            "external_write_repeated": False,
        }
    return {
        "schema_version": "executor-github-effect-restart-recovery/1.0",
        "status": "RECOVERED",
        "effect": result,
        "attempt_id": attempts[0].attempt_id,
        "effect_sha256": effect_sha256,
        "automatic_retry_allowed": False,
        "external_write_repeated": False,
    }
