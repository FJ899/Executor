from __future__ import annotations

import copy
from typing import Any

from executor.solution_proposal import (
    SolutionProposalError,
    validate_solution_proposal,
)


_RAW_PROPOSAL_KEYS = {
    "schema_version",
    "proposal_id",
    "contract_sha256",
    "repository",
    "source_commit",
    "source_tree",
    "mutations",
    "rationale",
    "evidence_plan",
    "provenance",
}

_VALIDATED_ARTIFACT_KEYS = {
    "proposal_id",
    "contract_sha256",
    "repository",
    "source_commit",
    "source_tree",
    "mutations",
    "rationale",
    "evidence_plan",
    "provenance",
    "provenance_sha256",
    "payload_sha256",
}


def runtime_solution_proposal(
    artifact: dict[str, Any],
    *,
    frozen_result: dict[str, Any],
) -> dict[str, Any]:
    """Return the canonical runtime proposal for a provider-produced artifact.

    The provider boundary returns ``ValidatedSolutionProposal``. Its persisted
    ``to_dict()`` representation carries two derived integrity hashes and omits
    the raw proposal schema marker. PilotRuntime intentionally validates the raw
    ``executor-solution-proposal/1.0`` shape. This bridge accepts either exact
    representation, revalidates all frozen bindings, and verifies both derived
    hashes before returning the raw runtime proposal.
    """

    if not isinstance(artifact, dict):
        raise SolutionProposalError("solution artifact must be an object")

    keys = set(artifact)
    if keys == _RAW_PROPOSAL_KEYS:
        raw = copy.deepcopy(artifact)
        validate_solution_proposal(raw, frozen_result=frozen_result)
        return raw

    if keys != _VALIDATED_ARTIFACT_KEYS:
        raise SolutionProposalError(
            "solution artifact is neither a raw proposal nor a validated provider artifact"
        )

    raw = {
        "schema_version": "executor-solution-proposal/1.0",
        "proposal_id": artifact["proposal_id"],
        "contract_sha256": artifact["contract_sha256"],
        "repository": artifact["repository"],
        "source_commit": artifact["source_commit"],
        "source_tree": artifact["source_tree"],
        "mutations": copy.deepcopy(artifact["mutations"]),
        "rationale": artifact["rationale"],
        "evidence_plan": copy.deepcopy(artifact["evidence_plan"]),
        "provenance": copy.deepcopy(artifact["provenance"]),
    }
    validated = validate_solution_proposal(raw, frozen_result=frozen_result)

    if artifact.get("provenance_sha256") != validated.provenance_sha256:
        raise SolutionProposalError("validated solution provenance hash mismatch")
    if artifact.get("payload_sha256") != validated.payload_sha256:
        raise SolutionProposalError("validated solution payload hash mismatch")
    return raw
