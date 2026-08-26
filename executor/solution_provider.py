from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from executor.github_trust import canonical_json
from executor.solution_proposal import (
    ValidatedSolutionProposal,
    materialize_solution_candidate,
    validate_solution_proposal,
)


class SolutionProviderError(RuntimeError):
    pass


class SolutionProvider(Protocol):
    """Zero-effect external intelligence boundary.

    Providers may reason over an exact frozen contract and return only an
    ``executor-solution-candidate/1.0`` value. They receive no effect authority,
    GitHub token, repository mutation handle, or Executor ledger capability.
    """

    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    def generate_candidate(
        self,
        *,
        frozen_contract: dict[str, Any],
        prompt: str,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ExternalIntelligence:
    provider: SolutionProvider

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    def generate_candidate(
        self,
        *,
        frozen_contract: dict[str, Any],
        prompt: str,
    ) -> dict[str, Any]:
        return self.provider.generate_candidate(
            frozen_contract=copy.deepcopy(frozen_contract),
            prompt=prompt,
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_binding(contract: dict[str, Any]) -> dict[str, Any]:
    request = contract.get("request_evidence")
    if not isinstance(request, dict):
        raise SolutionProviderError("frozen contract request evidence is missing")
    return {
        "repository": request.get("repository"),
        "issue_number": request.get("issue_number"),
        "issue_node_id": request.get("issue_node_id"),
        "body_sha256": request.get("body_sha256"),
    }


def _source_binding(contract: dict[str, Any]) -> dict[str, Any]:
    target = contract.get("target")
    if not isinstance(target, dict):
        raise SolutionProviderError("frozen contract target is missing")
    return {
        "repository": target.get("repository"),
        "commit": target.get("commit"),
        "tree": target.get("tree"),
    }


def build_solution_provenance(
    *,
    provider: SolutionProvider,
    frozen_result: dict[str, Any],
    prompt: str,
    generated_at: str | None = None,
    historical_candidate_relation: str = "NEW_FIX",
) -> dict[str, Any]:
    """Create provenance inside Executor at the provider trust boundary."""

    if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
        raise SolutionProviderError("solution generation requires a frozen contract")
    contract = frozen_result.get("contract")
    if not isinstance(contract, dict):
        raise SolutionProviderError("frozen contract is missing")
    if not isinstance(prompt, str) or not prompt:
        raise SolutionProviderError("provider prompt must be non-empty")
    provider_name = provider.provider_name
    model_name = provider.model_name
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise SolutionProviderError("provider name is required")
    if not isinstance(model_name, str) or not model_name.strip():
        raise SolutionProviderError("provider model is required")
    if historical_candidate_relation not in {"SAME_FIX_REDERIVED", "NEW_FIX"}:
        raise SolutionProviderError("historical candidate relation is invalid")

    return {
        "schema_version": "executor-solution-provenance/1.0",
        "producer_role": "EXTERNAL_INTELLIGENCE",
        "provider": provider_name.strip(),
        "model": model_name.strip(),
        "generated_at": generated_at or _utc_now(),
        "request": _request_binding(contract),
        "source": _source_binding(contract),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "human_solution_edits": 0,
        "effect_capability": "NONE",
        "derivation": "REGENERATED_AFTER_HUMAN_REQUEST",
        "historical_candidate_relation": historical_candidate_relation,
    }


def generate_validated_solution(
    *,
    provider: SolutionProvider,
    frozen_result: dict[str, Any],
    prompt: str,
    generated_at: str | None = None,
    historical_candidate_relation: str = "NEW_FIX",
) -> ValidatedSolutionProposal:
    """Frozen contract -> provider candidate -> Executor-owned provenance -> validation."""

    if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
        raise SolutionProviderError("solution generation requires AUTHORIZED_AND_FROZEN")
    candidate = provider.generate_candidate(
        frozen_contract=copy.deepcopy(frozen_result),
        prompt=prompt,
    )
    provenance = build_solution_provenance(
        provider=provider,
        frozen_result=frozen_result,
        prompt=prompt,
        generated_at=generated_at,
        historical_candidate_relation=historical_candidate_relation,
    )
    proposal = materialize_solution_candidate(
        candidate,
        frozen_result=frozen_result,
        provenance=provenance,
    )
    validated = validate_solution_proposal(proposal, frozen_result=frozen_result)
    # Defensive assertion: a provider can influence candidate content but cannot
    # override the boundary-owned provenance or inject effect authority.
    expected_sha = hashlib.sha256(canonical_json(provenance).encode("utf-8")).hexdigest()
    if validated.provenance_sha256 != expected_sha:
        raise SolutionProviderError("validated provenance differs from boundary-owned provenance")
    return validated
