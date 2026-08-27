from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from executor.github_trust import canonical_json
from executor.solution_context import SolutionContext, build_solution_context
from executor.solution_proposal import (
    ValidatedSolutionProposal,
    materialize_solution_candidate,
    validate_solution_proposal,
)
from executor.solution_source import GitSolutionSourceResolver, SourceObservation


class SolutionProviderError(RuntimeError):
    pass


class SolutionProvider(Protocol):
    """Zero-write external intelligence boundary.

    Providers receive only the frozen product artifact, an exact read-only
    SolutionContext and the prompt. They receive no repository writer, GitHub
    mutation client, publication handle, or authority ledger.
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
        solution_context: dict[str, Any],
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
        solution_context: dict[str, Any],
        prompt: str,
    ) -> dict[str, Any]:
        return self.provider.generate_candidate(
            frozen_contract=copy.deepcopy(frozen_contract),
            solution_context=copy.deepcopy(solution_context),
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
    solution_context: SolutionContext | None = None,
    source_observation: SourceObservation | None = None,
) -> dict[str, Any]:
    """Create provenance inside Executor at the provider boundary.

    Calls without SolutionContext/SourceObservation retain the historical 1.0
    shape for compatibility. The active Stage-2 generation path always supplies
    both and therefore emits provenance 1.1.
    """

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
    if (solution_context is None) != (source_observation is None):
        raise SolutionProviderError("solution context and source observation must be supplied together")

    common = {
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
    if solution_context is None or source_observation is None:
        return {
            "schema_version": "executor-solution-provenance/1.0",
            **common,
        }

    contract_sha256 = frozen_result.get("contract_sha256")
    if not isinstance(contract_sha256, str) or len(contract_sha256) != 64:
        raise SolutionProviderError("frozen contract hash is missing")
    if solution_context.contract_sha256 != contract_sha256:
        raise SolutionProviderError("solution context is bound to a different frozen contract")
    if solution_context.source_observation_id != source_observation.observation_id:
        raise SolutionProviderError("solution context source observation binding mismatch")

    return {
        "schema_version": "executor-solution-provenance/1.1",
        **common,
        "frozen_contract_sha256": contract_sha256,
        "solution_context_sha256": solution_context.sha256,
        "source_observation_id": source_observation.observation_id,
        "source_observed_at": source_observation.observed_at,
        "source_files": [item.identity_dict() for item in source_observation.files],
    }


def generate_validated_solution(
    *,
    provider: SolutionProvider,
    frozen_result: dict[str, Any],
    source_root: str | Path,
    prompt: str,
    generated_at: str | None = None,
    historical_candidate_relation: str = "NEW_FIX",
) -> ValidatedSolutionProposal:
    """Frozen contract -> exact source context -> provider -> validated proposal.

    The production path establishes the source observation internally with the
    canonical Git resolver. Callers supply only the checkout location, never a
    replacement observation adapter.
    """

    if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
        raise SolutionProviderError("solution generation requires AUTHORIZED_AND_FROZEN")
    try:
        observation = GitSolutionSourceResolver().observe(
            frozen_result=frozen_result,
            source_root=source_root,
        )
        context = build_solution_context(
            frozen_result=frozen_result,
            observation=observation,
        )
    except (RuntimeError, ValueError, OSError) as exc:
        raise SolutionProviderError(f"cannot establish exact solution source context: {exc}") from exc

    candidate = provider.generate_candidate(
        frozen_contract=copy.deepcopy(frozen_result),
        solution_context=context.to_dict(),
        prompt=prompt,
    )
    provenance = build_solution_provenance(
        provider=provider,
        frozen_result=frozen_result,
        prompt=prompt,
        generated_at=generated_at,
        historical_candidate_relation=historical_candidate_relation,
        solution_context=context,
        source_observation=observation,
    )
    proposal = materialize_solution_candidate(
        candidate,
        frozen_result=frozen_result,
        provenance=provenance,
    )
    validated = validate_solution_proposal(proposal, frozen_result=frozen_result)
    # Defensive assertion: a provider can influence candidate content but cannot
    # override the boundary-owned provenance or its context/source bindings.
    expected_sha = hashlib.sha256(canonical_json(provenance).encode("utf-8")).hexdigest()
    if validated.provenance_sha256 != expected_sha:
        raise SolutionProviderError("validated provenance differs from boundary-owned provenance")
    return validated
