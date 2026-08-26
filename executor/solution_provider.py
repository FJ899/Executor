from __future__ import annotations

import copy
import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from executor.frozen_pilot_authority import (
    FrozenPilotAuthorityError,
    validate_frozen_pilot_authority,
)
from executor.github_trust import canonical_json
from executor.repository_access import RepositoryPathError, canonical_repository_path
from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, verify_worktree_file
from executor.solution_proposal import (
    SolutionProposalError,
    ValidatedSolutionProposal,
    materialize_solution_candidate,
    validate_solution_proposal,
)


class SolutionProviderError(ValueError):
    pass


class SolutionGenerator(Protocol):
    """External intelligence adapter with no Executor effect-authority handle."""

    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    def generate(self, prompt: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class VerifiedGenerationEvidence:
    """Independent provider evidence for one exact generation response."""

    evidence_ref: str
    provider: str
    model: str
    generated_at: str
    frozen_contract_sha256: str
    repository: str
    commit: str
    tree: str
    context_sha256: str
    prompt_sha256: str
    response_sha256: str
    verification_method: str


class SolutionGenerationVerifier(Protocol):
    """Resolve immutable generation evidence independently of generator output."""

    def verify(self, evidence_ref: str) -> VerifiedGenerationEvidence: ...


@dataclass(frozen=True)
class SolutionSourceFile:
    path: str
    sha256: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "text": self.text,
        }


@dataclass(frozen=True)
class SolutionSourceContext:
    frozen_contract_sha256: str
    repository: str
    commit: str
    tree: str
    allowed_paths: tuple[str, ...]
    files: tuple[SolutionSourceFile, ...]
    context_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "executor-solution-context/1.0",
            "frozen_contract_sha256": self.frozen_contract_sha256,
            "repository": self.repository,
            "commit": self.commit,
            "tree": self.tree,
            "allowed_paths": list(self.allowed_paths),
            "files": [item.to_dict() for item in self.files],
            "context_sha256": self.context_sha256,
        }


@dataclass(frozen=True)
class SolutionProviderResult:
    proposal: dict[str, Any]
    validated: ValidatedSolutionProposal
    provider: str
    model: str
    context_sha256: str
    prompt_sha256: str
    generation_evidence_ref: str
    generation_response_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "executor-solution-provider-result/1.1",
            "status": "VALIDATED_SOLUTION_PROPOSAL",
            "provider": self.provider,
            "model": self.model,
            "context_sha256": self.context_sha256,
            "prompt_sha256": self.prompt_sha256,
            "generation_evidence_ref": self.generation_evidence_ref,
            "generation_response_sha256": self.generation_response_sha256,
            "proposal_sha256": self.validated.payload_sha256,
            "effect_capability": "NONE",
            "proposal": copy.deepcopy(self.proposal),
        }


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SolutionProviderError(f"cannot inspect solution source checkout: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SolutionProviderError(
            f"cannot inspect solution source checkout: git {' '.join(args)}: {detail}"
        )
    return completed.stdout.strip()


def _parse_utc(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise SolutionProviderError(f"{label} must be RFC3339 UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise SolutionProviderError(f"{label} is invalid") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise SolutionProviderError(f"{label} must be UTC")
    return parsed.astimezone(timezone.utc)


def _require_sha256(value: Any, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise SolutionProviderError(f"{label} must be lowercase SHA-256")
    return value


def _validated_contract(frozen_result: dict[str, Any]) -> tuple[dict[str, Any], str]:
    try:
        validate_frozen_pilot_authority(frozen_result)
    except FrozenPilotAuthorityError as exc:
        raise SolutionProviderError(f"invalid frozen authority: {exc}") from exc

    contract = frozen_result.get("contract")
    contract_sha256 = frozen_result.get("contract_sha256")
    if not isinstance(contract, dict) or not isinstance(contract_sha256, str):
        raise SolutionProviderError("frozen contract identity is missing")
    actual_contract_sha256 = _sha256_json(contract)
    if actual_contract_sha256 != contract_sha256:
        raise SolutionProviderError("frozen contract content hash mismatch")
    return contract, contract_sha256


def build_solution_source_context(
    *,
    frozen_result: dict[str, Any],
    checkout_root: str | Path,
) -> SolutionSourceContext:
    contract, contract_sha256 = _validated_contract(frozen_result)
    target = contract.get("target")
    task = contract.get("task")
    if not isinstance(target, dict) or not isinstance(task, dict):
        raise SolutionProviderError("frozen target/task is missing")

    repository = target.get("repository")
    commit = target.get("commit")
    tree = target.get("tree")
    if not all(isinstance(value, str) and value for value in (repository, commit, tree)):
        raise SolutionProviderError("frozen target identity is incomplete")

    try:
        root = verify_repository_checkout(
            checkout_root,
            repository=repository,
            commit=commit,
            require_head=True,
        )
    except RepositoryIdentityError as exc:
        raise SolutionProviderError(f"solution source identity mismatch: {exc}") from exc

    if _git(root, "rev-parse", "HEAD^{tree}") != tree:
        raise SolutionProviderError("solution source tree differs from frozen target tree")

    raw_allowed = task.get("allowed_paths")
    if not isinstance(raw_allowed, list) or not raw_allowed:
        raise SolutionProviderError("frozen solution scope is missing")
    allowed: list[str] = []
    seen: set[str] = set()
    for value in raw_allowed:
        try:
            path = canonical_repository_path(value)
        except (RepositoryPathError, TypeError) as exc:
            raise SolutionProviderError("frozen solution scope contains an invalid path") from exc
        if path in seen:
            raise SolutionProviderError("frozen solution scope contains duplicate paths")
        seen.add(path)
        allowed.append(path)

    files: list[SolutionSourceFile] = []
    for path in allowed:
        try:
            raw = verify_worktree_file(root, commit=commit, path=path)
        except (RepositorySnapshotError, RepositoryPathError) as exc:
            raise SolutionProviderError(
                f"solution source is stale or differs from commit: {path}: {exc}"
            ) from exc
        try:
            text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise SolutionProviderError(f"solution source is not UTF-8 text: {path}") from exc
        if "\x00" in text:
            raise SolutionProviderError(f"solution source contains NUL bytes: {path}")
        files.append(
            SolutionSourceFile(
                path=path,
                sha256=hashlib.sha256(raw).hexdigest(),
                text=text,
            )
        )

    context_payload = {
        "schema_version": "executor-solution-context/1.0",
        "frozen_contract_sha256": contract_sha256,
        "repository": repository,
        "commit": commit,
        "tree": tree,
        "allowed_paths": allowed,
        "files": [item.to_dict() for item in files],
    }
    return SolutionSourceContext(
        frozen_contract_sha256=contract_sha256,
        repository=repository,
        commit=commit,
        tree=tree,
        allowed_paths=tuple(allowed),
        files=tuple(files),
        context_sha256=_sha256_json(context_payload),
    )


def _build_prompt(
    *,
    contract: dict[str, Any],
    context: SolutionSourceContext,
) -> dict[str, Any]:
    return {
        "schema_version": "executor-solution-provider-prompt/1.1",
        "instruction": (
            "Propose the smallest code replacement that satisfies the frozen task. "
            "Do not expand scope, weaken protected material, or claim effect authority. "
            "The adapter must return an immutable provider generation evidence_ref for "
            "this exact response; stale or cross-invocation evidence is invalid."
        ),
        "frozen_contract_sha256": context.frozen_contract_sha256,
        "target": copy.deepcopy(contract["target"]),
        "task": copy.deepcopy(contract["task"]),
        "source_context": context.to_dict(),
        "output_contract": {
            "schema_version": "executor-solution-generation/1.1",
            "fields": ["evidence_ref", "mutations", "rationale"],
            "mutation_fields": ["path", "replacement_text"],
            "effect_capability": "NONE",
        },
    }


def _normalize_generation(
    generation: Any,
    *,
    context: SolutionSourceContext,
    contract: dict[str, Any],
) -> tuple[list[dict[str, str]], str, str, str]:
    expected = {"schema_version", "evidence_ref", "mutations", "rationale"}
    if not isinstance(generation, dict) or set(generation) != expected:
        raise SolutionProviderError("solution generator returned invalid fields")
    if generation.get("schema_version") != "executor-solution-generation/1.1":
        raise SolutionProviderError("solution generator schema is invalid")
    evidence_ref = generation.get("evidence_ref")
    if not isinstance(evidence_ref, str) or not evidence_ref.strip():
        raise SolutionProviderError("solution generator evidence_ref is required")
    rationale = generation.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise SolutionProviderError("solution generator rationale is required")

    raw_mutations = generation.get("mutations")
    maximum = contract["task"].get("max_production_files")
    if type(maximum) is not int or maximum < 1:
        raise SolutionProviderError("frozen production-file bound is invalid")
    if not isinstance(raw_mutations, list) or not 1 <= len(raw_mutations) <= maximum:
        raise SolutionProviderError("solution generator exceeds the frozen file bound")

    response_payload = {
        "schema_version": generation["schema_version"],
        "mutations": copy.deepcopy(raw_mutations),
        "rationale": rationale,
    }
    response_sha256 = _sha256_json(response_payload)

    source_by_path = {item.path: item for item in context.files}
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_mutations):
        if not isinstance(item, dict) or set(item) != {"path", "replacement_text"}:
            raise SolutionProviderError(f"solution generator mutation {index} is malformed")
        try:
            path = canonical_repository_path(item.get("path"))
        except (RepositoryPathError, TypeError) as exc:
            raise SolutionProviderError(
                f"solution generator mutation {index} path is invalid"
            ) from exc
        if path not in source_by_path:
            raise SolutionProviderError(
                f"solution generator attempted scope expansion: {path}"
            )
        if path in seen:
            raise SolutionProviderError("solution generator returned duplicate mutation paths")
        seen.add(path)
        replacement = item.get("replacement_text")
        if not isinstance(replacement, str) or "\x00" in replacement:
            raise SolutionProviderError(
                f"solution generator mutation {index} replacement is invalid"
            )
        source = source_by_path[path]
        if replacement == source.text:
            raise SolutionProviderError(
                f"solution generator mutation {index} is a no-op"
            )
        normalized.append(
            {
                "path": path,
                "expected_before_sha256": source.sha256,
                "replacement_text": replacement,
                "expected_after_sha256": hashlib.sha256(
                    replacement.encode("utf-8")
                ).hexdigest(),
            }
        )
    return normalized, rationale.strip(), evidence_ref.strip(), response_sha256


def _validate_generation_evidence(
    evidence: Any,
    *,
    evidence_ref: str,
    response_sha256: str,
    provider: str,
    model: str,
    contract: dict[str, Any],
    contract_sha256: str,
    context: SolutionSourceContext,
    prompt_sha256: str,
) -> VerifiedGenerationEvidence:
    if not isinstance(evidence, VerifiedGenerationEvidence):
        raise SolutionProviderError("generation verifier returned invalid evidence")
    if evidence.evidence_ref != evidence_ref:
        raise SolutionProviderError("generation evidence reference mismatch")
    if evidence.provider != provider or evidence.model != model:
        raise SolutionProviderError("generation evidence producer mismatch")
    if evidence.frozen_contract_sha256 != contract_sha256:
        raise SolutionProviderError("generation evidence frozen contract mismatch")
    if (
        evidence.repository != context.repository
        or evidence.commit != context.commit
        or evidence.tree != context.tree
    ):
        raise SolutionProviderError("generation evidence source mismatch")
    if evidence.context_sha256 != context.context_sha256:
        raise SolutionProviderError("generation evidence context mismatch")
    if evidence.prompt_sha256 != prompt_sha256:
        raise SolutionProviderError("generation evidence prompt mismatch")
    if _require_sha256(evidence.response_sha256, label="generation response hash") != response_sha256:
        raise SolutionProviderError("generation evidence response hash mismatch")
    if not isinstance(evidence.verification_method, str) or not evidence.verification_method.strip():
        raise SolutionProviderError("generation verification method is required")

    generated_at = _parse_utc(evidence.generated_at, label="generation evidence generated_at")
    snapshot = contract.get("authority_snapshot")
    if not isinstance(snapshot, dict):
        raise SolutionProviderError("frozen authority snapshot is missing")
    frozen_at = _parse_utc(snapshot.get("verified_at"), label="authority snapshot verified_at")
    if generated_at <= frozen_at:
        raise SolutionProviderError("verified generation does not postdate frozen contract")
    return evidence


class SolutionProvider:
    """Bind independently verified external intelligence to one exact frozen proposal."""

    def __init__(
        self,
        generator: SolutionGenerator,
        generation_verifier: SolutionGenerationVerifier,
    ) -> None:
        self._generator = generator
        self._generation_verifier = generation_verifier
        provider = getattr(generator, "provider", None)
        model = getattr(generator, "model", None)
        if not isinstance(provider, str) or not provider.strip():
            raise SolutionProviderError("solution generator provider identity is required")
        if not isinstance(model, str) or not model.strip():
            raise SolutionProviderError("solution generator model identity is required")
        self.provider = provider.strip()
        self.model = model.strip()

    def provide(
        self,
        *,
        frozen_result: dict[str, Any],
        checkout_root: str | Path,
    ) -> SolutionProviderResult:
        contract, contract_sha256 = _validated_contract(frozen_result)
        context = build_solution_source_context(
            frozen_result=frozen_result,
            checkout_root=checkout_root,
        )
        prompt = _build_prompt(contract=contract, context=context)
        prompt_sha256 = _sha256_json(prompt)
        try:
            generation = self._generator.generate(copy.deepcopy(prompt))
        except Exception as exc:  # adapter failure is data-plane failure, never authority
            raise SolutionProviderError(f"solution generator failed: {exc}") from exc
        mutations, rationale, evidence_ref, response_sha256 = _normalize_generation(
            generation,
            context=context,
            contract=contract,
        )
        try:
            raw_evidence = self._generation_verifier.verify(evidence_ref)
        except Exception as exc:
            raise SolutionProviderError(f"generation evidence verification failed: {exc}") from exc
        verified_generation = _validate_generation_evidence(
            raw_evidence,
            evidence_ref=evidence_ref,
            response_sha256=response_sha256,
            provider=self.provider,
            model=self.model,
            contract=contract,
            contract_sha256=contract_sha256,
            context=context,
            prompt_sha256=prompt_sha256,
        )

        generation_binding = {
            "frozen_contract_sha256": contract_sha256,
            "context_sha256": context.context_sha256,
            "prompt_sha256": prompt_sha256,
            "generation_evidence_ref": verified_generation.evidence_ref,
            "generation_response_sha256": verified_generation.response_sha256,
        }
        proposal_id = f"proposal-{_sha256_json(generation_binding)[:24]}"
        task = contract["task"]
        candidate = {
            "schema_version": "executor-solution-candidate/1.0",
            "status": "AWAITING_FROZEN_CONTRACT_SHA",
            "proposal_id": proposal_id,
            "repository": context.repository,
            "source_commit": context.commit,
            "source_tree": context.tree,
            "mutations": mutations,
            "rationale": rationale,
            "evidence_plan": [
                *copy.deepcopy(task["postcondition_argv"]),
                *copy.deepcopy(task["regression_argv"]),
            ],
        }
        request_evidence = contract["request_evidence"]
        provenance = {
            "schema_version": "executor-solution-provenance/1.2",
            "producer_role": "EXTERNAL_INTELLIGENCE",
            "provider": verified_generation.provider,
            "model": verified_generation.model,
            "generated_at": verified_generation.generated_at,
            "request": {
                "repository": request_evidence["repository"],
                "issue_number": request_evidence["issue_number"],
                "issue_node_id": request_evidence["issue_node_id"],
                "body_sha256": request_evidence["body_sha256"],
            },
            "frozen_contract_sha256": verified_generation.frozen_contract_sha256,
            "source": {
                "repository": verified_generation.repository,
                "commit": verified_generation.commit,
                "tree": verified_generation.tree,
            },
            "context_sha256": verified_generation.context_sha256,
            "prompt_sha256": verified_generation.prompt_sha256,
            "generation_evidence_ref": verified_generation.evidence_ref,
            "generation_response_sha256": verified_generation.response_sha256,
            "generation_verification_method": verified_generation.verification_method,
            "human_solution_edits": 0,
            "effect_capability": "NONE",
            "derivation": "GENERATED_AFTER_FROZEN_CONTRACT",
            "historical_candidate_relation": "NEW_FIX",
        }
        try:
            proposal = materialize_solution_candidate(
                candidate,
                frozen_result=frozen_result,
                provenance=provenance,
            )
            validated = validate_solution_proposal(
                proposal,
                frozen_result=frozen_result,
            )
        except SolutionProposalError as exc:
            raise SolutionProviderError(f"generated solution proposal is invalid: {exc}") from exc
        return SolutionProviderResult(
            proposal=copy.deepcopy(proposal),
            validated=validated,
            provider=self.provider,
            model=self.model,
            context_sha256=context.context_sha256,
            prompt_sha256=prompt_sha256,
            generation_evidence_ref=verified_generation.evidence_ref,
            generation_response_sha256=verified_generation.response_sha256,
        )
