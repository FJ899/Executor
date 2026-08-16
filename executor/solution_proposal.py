from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any

from executor.github_trust import canonical_json
from executor.repository_access import RepositoryPathError, canonical_repository_path


class SolutionProposalError(ValueError):
    pass


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_KEYS = {
    "authority",
    "authorization",
    "approved",
    "accept",
    "merge",
    "deploy",
    "secrets",
    "network",
}


@dataclass(frozen=True)
class ProposedMutation:
    path: str
    expected_before_sha256: str
    replacement_text: str
    expected_after_sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "expected_before_sha256": self.expected_before_sha256,
            "replacement_text": self.replacement_text,
            "expected_after_sha256": self.expected_after_sha256,
        }


@dataclass(frozen=True)
class ValidatedSolutionProposal:
    proposal_id: str
    contract_sha256: str
    repository: str
    source_commit: str
    source_tree: str
    mutations: tuple[ProposedMutation, ...]
    rationale: str
    evidence_plan: tuple[tuple[str, ...], ...]
    payload_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "contract_sha256": self.contract_sha256,
            "repository": self.repository,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "mutations": [item.to_dict() for item in self.mutations],
            "rationale": self.rationale,
            "evidence_plan": [list(item) for item in self.evidence_plan],
            "payload_sha256": self.payload_sha256,
        }


def materialize_solution_candidate(
    candidate: dict[str, Any],
    *,
    frozen_result: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(candidate, dict) or set(candidate) != {
        "schema_version",
        "status",
        "proposal_id",
        "repository",
        "source_commit",
        "source_tree",
        "mutations",
        "rationale",
        "evidence_plan",
    }:
        raise SolutionProposalError("solution candidate has invalid fields")
    if (
        candidate.get("schema_version") != "executor-solution-candidate/1.0"
        or candidate.get("status") != "AWAITING_FROZEN_CONTRACT_SHA"
    ):
        raise SolutionProposalError("solution candidate status/schema is invalid")
    proposal = {
        "schema_version": "executor-solution-proposal/1.0",
        "proposal_id": candidate["proposal_id"],
        "contract_sha256": frozen_result.get("contract_sha256"),
        "repository": candidate["repository"],
        "source_commit": candidate["source_commit"],
        "source_tree": candidate["source_tree"],
        "mutations": copy.deepcopy(candidate["mutations"]),
        "rationale": candidate["rationale"],
        "evidence_plan": copy.deepcopy(candidate["evidence_plan"]),
    }
    validate_solution_proposal(proposal, frozen_result=frozen_result)
    return proposal


def _find_forbidden_keys(value: Any, *, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in _FORBIDDEN_KEYS:
                found.append(f"{path}.{key}")
            found.extend(_find_forbidden_keys(child, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_find_forbidden_keys(child, path=f"{path}[{index}]"))
    return found


def validate_solution_proposal(
    proposal: dict[str, Any],
    *,
    frozen_result: dict[str, Any],
) -> ValidatedSolutionProposal:
    if not isinstance(proposal, dict):
        raise SolutionProposalError("solution proposal must be an object")
    expected_keys = {
        "schema_version",
        "proposal_id",
        "contract_sha256",
        "repository",
        "source_commit",
        "source_tree",
        "mutations",
        "rationale",
        "evidence_plan",
    }
    if set(proposal) != expected_keys:
        raise SolutionProposalError("solution proposal has missing or additional fields")
    forbidden = _find_forbidden_keys(proposal)
    if forbidden:
        raise SolutionProposalError(
            f"solution proposal attempts to carry effect authority: {forbidden}"
        )
    if proposal.get("schema_version") != "executor-solution-proposal/1.0":
        raise SolutionProposalError("unsupported solution proposal schema")
    if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
        raise SolutionProposalError("no authorized frozen contract is available")
    contract = frozen_result.get("contract")
    if not isinstance(contract, dict):
        raise SolutionProposalError("frozen contract is missing")
    contract_sha = frozen_result.get("contract_sha256")
    if proposal.get("contract_sha256") != contract_sha:
        raise SolutionProposalError("solution proposal is bound to a different contract")
    proposal_id = proposal.get("proposal_id")
    if not isinstance(proposal_id, str) or _SAFE_ID.fullmatch(proposal_id) is None:
        raise SolutionProposalError("proposal_id is invalid")

    target = contract["target"]
    for field in ("repository", "source_commit", "source_tree"):
        proposal_field = {
            "repository": "repository",
            "source_commit": "commit",
            "source_tree": "tree",
        }[field]
        if proposal.get(field) != target.get(proposal_field):
            raise SolutionProposalError(f"solution proposal {field} mismatch")
    if not isinstance(proposal.get("rationale"), str) or not proposal[
        "rationale"
    ].strip():
        raise SolutionProposalError("solution proposal rationale is required")

    mutations = proposal.get("mutations")
    maximum = contract["task"]["max_production_files"]
    if not isinstance(mutations, list) or not 1 <= len(mutations) <= maximum:
        raise SolutionProposalError("solution proposal exceeds the production-file bound")
    allowed = set(contract["task"]["allowed_paths"])
    protected = tuple(contract["task"]["protected_paths"])
    normalized: list[ProposedMutation] = []
    seen: set[str] = set()
    for index, item in enumerate(mutations):
        if not isinstance(item, dict) or set(item) != {
            "path",
            "expected_before_sha256",
            "replacement_text",
            "expected_after_sha256",
        }:
            raise SolutionProposalError(f"mutation {index} has invalid fields")
        try:
            path = canonical_repository_path(item.get("path"))
        except (RepositoryPathError, TypeError) as exc:
            raise SolutionProposalError(f"mutation {index} path is invalid") from exc
        if path not in allowed or any(fnmatch(path, pattern) for pattern in protected):
            raise SolutionProposalError(f"mutation path is outside the frozen scope: {path}")
        if path in seen:
            raise SolutionProposalError("solution proposal contains duplicate paths")
        seen.add(path)
        before = item.get("expected_before_sha256")
        after = item.get("expected_after_sha256")
        replacement = item.get("replacement_text")
        if (
            not isinstance(before, str)
            or _SHA256.fullmatch(before) is None
            or not isinstance(after, str)
            or _SHA256.fullmatch(after) is None
            or not isinstance(replacement, str)
            or "\x00" in replacement
        ):
            raise SolutionProposalError(f"mutation {index} hashes/content are invalid")
        actual_after = hashlib.sha256(replacement.encode("utf-8")).hexdigest()
        if actual_after != after:
            raise SolutionProposalError(
                f"mutation {index} replacement does not match after hash"
            )
        normalized.append(
            ProposedMutation(
                path=path,
                expected_before_sha256=before,
                replacement_text=replacement,
                expected_after_sha256=after,
            )
        )

    evidence_plan = proposal.get("evidence_plan")
    if not isinstance(evidence_plan, list) or not evidence_plan:
        raise SolutionProposalError("solution proposal evidence_plan is required")
    commands: list[tuple[str, ...]] = []
    for index, command in enumerate(evidence_plan):
        if not isinstance(command, list) or not command or not all(
            isinstance(item, str) and item and "\x00" not in item for item in command
        ):
            raise SolutionProposalError(f"evidence_plan[{index}] is not argv")
        commands.append(tuple(command))
    required_commands = {
        tuple(item)
        for key in ("postcondition_argv", "regression_argv")
        for item in contract["task"][key]
    }
    if not required_commands.issubset(set(commands)):
        raise SolutionProposalError("evidence plan omits frozen verification commands")
    payload_sha = hashlib.sha256(canonical_json(proposal).encode("utf-8")).hexdigest()
    return ValidatedSolutionProposal(
        proposal_id=proposal_id,
        contract_sha256=contract_sha,
        repository=proposal["repository"],
        source_commit=proposal["source_commit"],
        source_tree=proposal["source_tree"],
        mutations=tuple(normalized),
        rationale=proposal["rationale"],
        evidence_plan=tuple(commands),
        payload_sha256=payload_sha,
    )
