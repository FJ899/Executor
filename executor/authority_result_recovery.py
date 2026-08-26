from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from executor.authority_ledger import AuthorityLedgerError
from executor.github_authority import GovernedAuthorityConsumption, GovernedAuthorityLedger
from executor.github_trust import canonical_json


class AuthorityResultRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorityResultRecovery:
    status: str
    result_sha256: str
    local: dict[str, Any]
    global_binding: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "executor-authority-result-recovery/1.0",
            "status": self.status,
            "result_sha256": self.result_sha256,
            "local": self.local,
            "global": self.global_binding,
            "external_effect_retry_allowed": False,
        }


def recover_local_result_binding(
    *,
    ledger: GovernedAuthorityLedger,
    consumption: GovernedAuthorityConsumption,
    result: dict[str, Any],
    global_binding: dict[str, Any],
) -> AuthorityResultRecovery:
    """Complete only the missing local binding; never repeat the external effect.

    This is the explicit recovery path for:

        global result bound + local result unbound

    The already-provider-bound result hash is authoritative. Recovery succeeds
    only when the caller supplies the identical result bytes and exact original
    local execution token.
    """

    if not isinstance(global_binding, dict):
        raise AuthorityResultRecoveryError("global_binding must be an object")
    expected = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
    if global_binding.get("result_sha256") != expected:
        raise AuthorityResultRecoveryError(
            "recovery result differs from the already-bound global result"
        )
    if global_binding.get("authority_key") != consumption.authority_key:
        raise AuthorityResultRecoveryError("global binding authority key mismatch")
    if global_binding.get("payload_sha256") != consumption.payload_sha256:
        raise AuthorityResultRecoveryError("global binding payload mismatch")
    if global_binding.get("action_kind") != consumption.action_kind:
        raise AuthorityResultRecoveryError("global binding action kind mismatch")
    if global_binding.get("run_id") != consumption.run_id:
        raise AuthorityResultRecoveryError("global binding run mismatch")
    try:
        local = ledger.local.bind_result(
            execution_token=consumption.execution_token,
            result=result,
        )
    except AuthorityLedgerError as exc:
        raise AuthorityResultRecoveryError(
            "local result binding is still incomplete; external effect must not be repeated"
        ) from exc
    if local.result_sha256 != expected:
        raise AuthorityResultRecoveryError("local recovery result hash mismatch")
    return AuthorityResultRecovery(
        status="GLOBAL_AND_LOCAL_RESULT_BOUND",
        result_sha256=expected,
        local=local.to_dict(),
        global_binding=global_binding,
    )
