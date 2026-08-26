from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from executor.github_authority import GovernedAuthorityLedger
from executor.github_trust import (
    GitHubEvidenceSource,
    GitHubTrustProfile,
    VerifiedGitHubDecision,
    VerifiedGitHubRequest,
)
from executor.pilot_contract import (
    apply_github_decision,
    build_pilot_draft_from_formation,
)
from executor.request_to_contract import FormationStatus, RequestToContract001
from executor.solution_provider import SolutionProvider, generate_validated_solution
from executor.solution_proposal import ValidatedSolutionProposal


class ProductFlowError(RuntimeError):
    pass


@dataclass
class FormationPilotFlow:
    """Canonical product path: natural request -> publication -> decision -> frozen -> solution.

    Formation is the semantic source of the request. GitHub Issue publication is
    a system transport with zero human authority. Only the later provider-verified
    ACCEPT/MODIFY/REJECT is human authority.
    """

    formation: RequestToContract001

    def authorization_request(self) -> dict[str, Any]:
        return self.formation.export_human_authorization_request()

    def build_verified_draft(
        self,
        request: VerifiedGitHubRequest,
        *,
        publication: dict[str, Any],
    ) -> dict[str, Any]:
        canonical = self.formation.canonical_pilot_request()
        return build_pilot_draft_from_formation(
            canonical,
            request,
            formation_publication=publication,
        )

    def apply_verified_decision(
        self,
        *,
        request: VerifiedGitHubRequest,
        decision: VerifiedGitHubDecision,
        publication: dict[str, Any],
        source: GitHubEvidenceSource,
        profile: GitHubTrustProfile,
        ledger: GovernedAuthorityLedger,
    ) -> dict[str, Any]:
        if self.formation.status is not FormationStatus.AWAITING_VERIFIED_HUMAN_AUTHORIZATION:
            raise ProductFlowError("formation is not awaiting a verified human decision")
        canonical = self.formation.canonical_pilot_request()
        draft = build_pilot_draft_from_formation(
            canonical,
            request,
            formation_publication=publication,
        )
        result = apply_github_decision(
            draft=draft,
            decision=decision,
            source=source,
            profile=profile,
            ledger=ledger,
            formation_request=canonical,
            formation_publication=publication,
        )
        state_result = copy.deepcopy(result)
        formation_binding = result.get("formation_binding")
        if isinstance(formation_binding, dict):
            state_result["draft_sha256"] = formation_binding.get("draft_sha256")
        self.formation.apply_authority_result(state_result)
        return result

    def begin_revision(self, *, user_request: str | None = None) -> None:
        self.formation.begin_revision(user_request=user_request)

    def frozen_result(self) -> dict[str, Any]:
        return self.formation.frozen_task_contract()

    def generate_solution(
        self,
        *,
        provider: SolutionProvider,
        prompt: str,
        generated_at: str | None = None,
        historical_candidate_relation: str = "NEW_FIX",
    ) -> ValidatedSolutionProposal:
        frozen = self.frozen_result()
        return generate_validated_solution(
            provider=provider,
            frozen_result=frozen,
            prompt=prompt,
            generated_at=generated_at,
            historical_candidate_relation=historical_candidate_relation,
        )
