from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Any

from executor.github_trust import canonical_json
from executor.repository_access import RepositoryPathError, canonical_repository_path
from executor.solution_context import (
    solution_context_identity_sha256,
    source_observation_identity_sha256,
)


class SolutionProposalError(ValueError):
    pass


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SHA1 = re.compile(r"^[0-9a-f]{40}$")
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
    provenance: dict[str, Any]
    provenance_sha256: str
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
            "provenance": copy.deepcopy(self.provenance),
            "provenance_sha256": self.provenance_sha256,
            "payload_sha256": self.payload_sha256,
        }


def materialize_solution_candidate(
    candidate: dict[str, Any],
    *,
    frozen_result: dict[str, Any],
    provenance: dict[str, Any],
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
        "provenance": copy.deepcopy(provenance),
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


def _parse_utc(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SolutionProposalError(f"{label} must be RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SolutionProposalError(f"{label} is invalid") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise SolutionProposalError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _validate_source_files_v11(
    value: Any,
    *,
    contract: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise SolutionProposalError("solution provenance source_files are required")
    task = contract.get("task")
    if not isinstance(task, dict):
        raise SolutionProposalError("frozen task is missing")
    allowed = task.get("allowed_paths")
    if not isinstance(allowed, list):
        raise SolutionProposalError("frozen allowed_paths are missing")
    expected_paths = [canonical_repository_path(path) for path in allowed]
    normalized: list[dict[str, str]] = []
    hashes: dict[str, str] = {}
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "git_blob_sha"}:
            raise SolutionProposalError(f"provenance.source_files[{index}] has invalid fields")
        try:
            path = canonical_repository_path(item.get("path"))
        except (RepositoryPathError, TypeError) as exc:
            raise SolutionProposalError(f"provenance.source_files[{index}] path is invalid") from exc
        sha = item.get("sha256")
        blob = item.get("git_blob_sha")
        if not isinstance(sha, str) or _SHA256.fullmatch(sha) is None:
            raise SolutionProposalError(f"provenance source file sha256 is invalid: {path}")
        if not isinstance(blob, str) or _SHA1.fullmatch(blob) is None:
            raise SolutionProposalError(f"provenance source file git blob SHA is invalid: {path}")
        normalized.append({"path": path, "sha256": sha, "git_blob_sha": blob})
        hashes[path] = sha
    if [item["path"] for item in normalized] != expected_paths:
        raise SolutionProposalError("solution provenance source_files do not match exact allowed_paths")
    if len(hashes) != len(normalized):
        raise SolutionProposalError("solution provenance source_files contain duplicate paths")
    return normalized, hashes


def _validate_provenance(
    value: Any,
    *,
    contract: dict[str, Any],
    contract_sha256: str,
) -> tuple[dict[str, Any], str, dict[str, str] | None]:
    common = {
        "schema_version",
        "producer_role",
        "provider",
        "model",
        "generated_at",
        "request",
        "source",
        "prompt_sha256",
        "human_solution_edits",
        "effect_capability",
        "derivation",
        "historical_candidate_relation",
    }
    v11_extra = {
        "frozen_contract_sha256",
        "solution_context_sha256",
        "source_observation_id",
        "source_observed_at",
        "source_files",
    }
    if not isinstance(value, dict):
        raise SolutionProposalError("solution provenance has invalid fields")
    schema = value.get("schema_version")
    if schema == "executor-solution-provenance/1.0":
        if set(value) != common:
            raise SolutionProposalError("solution provenance has invalid fields")
    elif schema == "executor-solution-provenance/1.1":
        if set(value) != common | v11_extra:
            raise SolutionProposalError("solution provenance has invalid fields")
    else:
        raise SolutionProposalError("solution provenance schema is invalid")

    if value.get("producer_role") != "EXTERNAL_INTELLIGENCE":
        raise SolutionProposalError("solution must be produced by external intelligence")
    if not isinstance(value.get("provider"), str) or not value["provider"].strip():
        raise SolutionProposalError("solution provenance provider is required")
    if not isinstance(value.get("model"), str) or not value["model"].strip():
        raise SolutionProposalError("solution provenance model is required")
    if value.get("human_solution_edits") != 0:
        raise SolutionProposalError("human solution edits must be zero")
    if value.get("effect_capability") != "NONE":
        raise SolutionProposalError("solution producer must have no effect capability")
    if value.get("derivation") != "REGENERATED_AFTER_HUMAN_REQUEST":
        raise SolutionProposalError("solution provenance must be post-request regeneration")
    if value.get("historical_candidate_relation") not in {
        "SAME_FIX_REDERIVED",
        "NEW_FIX",
    }:
        raise SolutionProposalError("historical candidate relation is invalid")
    prompt_sha = value.get("prompt_sha256")
    if not isinstance(prompt_sha, str) or _SHA256.fullmatch(prompt_sha) is None:
        raise SolutionProposalError("solution provenance prompt hash is invalid")

    request = value.get("request")
    request_evidence = contract.get("request_evidence", {})
    request_expected = {
        "repository": request_evidence.get("repository"),
        "issue_number": request_evidence.get("issue_number"),
        "issue_node_id": request_evidence.get("issue_node_id"),
        "body_sha256": request_evidence.get("body_sha256"),
    }
    if not isinstance(request, dict) or request != request_expected:
        raise SolutionProposalError("solution provenance request binding mismatch")

    target = contract.get("target", {})
    source_expected = {
        "repository": target.get("repository"),
        "commit": target.get("commit"),
        "tree": target.get("tree"),
    }
    if value.get("source") != source_expected:
        raise SolutionProposalError("solution provenance source binding mismatch")

    generated = _parse_utc(value.get("generated_at"), label="provenance.generated_at")
    request_created = _parse_utc(
        request_evidence.get("created_at"), label="request_evidence.created_at"
    )
    if generated <= request_created:
        raise SolutionProposalError("solution provenance predates the human request")

    source_hashes: dict[str, str] | None = None
    if schema == "executor-solution-provenance/1.1":
        if value.get("frozen_contract_sha256") != contract_sha256:
            raise SolutionProposalError("solution provenance frozen contract hash mismatch")
        context_sha = value.get("solution_context_sha256")
        observation_id = value.get("source_observation_id")
        if not isinstance(context_sha, str) or _SHA256.fullmatch(context_sha) is None:
            raise SolutionProposalError("solution provenance context hash is invalid")
        if not isinstance(observation_id, str) or _SHA256.fullmatch(observation_id) is None:
            raise SolutionProposalError("solution provenance source observation id is invalid")
        _parse_utc(value.get("source_observed_at"), label="provenance.source_observed_at")
        source_files, source_hashes = _validate_source_files_v11(
            value.get("source_files"),
            contract=contract,
        )
        expected_observation_id = source_observation_identity_sha256(
            repository=target.get("repository"),
            commit=target.get("commit"),
            tree=target.get("tree"),
            source_files=source_files,
        )
        if observation_id != expected_observation_id:
            raise SolutionProposalError("solution provenance source observation identity mismatch")
        expected_context_sha = solution_context_identity_sha256(
            contract_sha256=contract_sha256,
            contract=contract,
            source_files=source_files,
        )
        if context_sha != expected_context_sha:
            raise SolutionProposalError("solution provenance context hash mismatch")

    normalized = copy.deepcopy(value)
    sha = hashlib.sha256(canonical_json(normalized).encode("utf-8")).hexdigest()
    return normalized, sha, source_hashes


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
        "provenance",
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
    if not isinstance(proposal.get("rationale"), str) or not proposal["rationale"].strip():
        raise SolutionProposalError("solution proposal rationale is required")

    provenance, provenance_sha, source_hashes = _validate_provenance(
        proposal.get("provenance"),
        contract=contract,
        contract_sha256=contract_sha,
    )

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
        if source_hashes is not None and before != source_hashes.get(path):
            raise SolutionProposalError(
                f"mutation {index} before hash does not match exact frozen source"
            )
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
        provenance=provenance,
        provenance_sha256=provenance_sha,
        payload_sha256=payload_sha,
    )
