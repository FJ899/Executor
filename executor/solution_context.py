from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from typing import Any, Iterable

from executor.github_trust import canonical_json
from executor.repository_access import canonical_repository_path


class SolutionContextError(ValueError):
    pass


@dataclass(frozen=True)
class SourceFileContext:
    path: str
    content: str
    sha256: str
    git_blob_sha: str

    def identity_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "git_blob_sha": self.git_blob_sha,
        }

    def to_dict(self) -> dict[str, str]:
        return {
            **self.identity_dict(),
            "content": self.content,
        }


def _source_file_identities(files: Iterable[SourceFileContext | dict[str, Any]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in files:
        if isinstance(item, SourceFileContext):
            value = item.identity_dict()
        elif isinstance(item, dict):
            value = {
                "path": item.get("path"),
                "sha256": item.get("sha256"),
                "git_blob_sha": item.get("git_blob_sha"),
            }
        else:
            raise SolutionContextError("source file identity must be an object")
        try:
            path = canonical_repository_path(value["path"])
        except (TypeError, ValueError) as exc:
            raise SolutionContextError("source file path is invalid") from exc
        sha256 = value["sha256"]
        blob = value["git_blob_sha"]
        if not isinstance(sha256, str) or len(sha256) != 64:
            raise SolutionContextError(f"source file sha256 is invalid: {path}")
        if not isinstance(blob, str) or len(blob) != 40:
            raise SolutionContextError(f"source file git blob SHA is invalid: {path}")
        normalized.append({"path": path, "sha256": sha256, "git_blob_sha": blob})
    return normalized


def source_observation_identity_sha256(
    *,
    repository: str,
    commit: str,
    tree: str,
    source_files: Iterable[SourceFileContext | dict[str, Any]],
) -> str:
    payload = {
        "repository": repository,
        "commit": commit,
        "tree": tree,
        "source_files": _source_file_identities(source_files),
    }
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def solution_context_identity_payload(
    *,
    contract_sha256: str,
    contract: dict[str, Any],
    source_files: Iterable[SourceFileContext | dict[str, Any]],
) -> dict[str, Any]:
    target = contract.get("target")
    task = contract.get("task")
    if not isinstance(target, dict) or not isinstance(task, dict):
        raise SolutionContextError("frozen contract target/task is missing")
    allowed = task.get("allowed_paths")
    protected = task.get("protected_paths")
    postcondition = task.get("postcondition_argv")
    regression = task.get("regression_argv")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise SolutionContextError("frozen allowed_paths are invalid")
    if not isinstance(protected, list) or not all(isinstance(item, str) for item in protected):
        raise SolutionContextError("frozen protected_paths are invalid")
    if not isinstance(postcondition, list) or not isinstance(regression, list):
        raise SolutionContextError("frozen verification commands are invalid")
    identities = _source_file_identities(source_files)
    expected_paths = [canonical_repository_path(path) for path in allowed]
    if [item["path"] for item in identities] != expected_paths:
        raise SolutionContextError("source context does not cover exact allowed_paths in contract order")
    return {
        "request_id": contract.get("request_id"),
        "contract_sha256": contract_sha256,
        "repository": target.get("repository"),
        "source_commit": target.get("commit"),
        "source_tree": target.get("tree"),
        "allowed_paths": expected_paths,
        "protected_paths": copy.deepcopy(protected),
        "source_files": identities,
        "success_criteria": {
            "postcondition_argv": copy.deepcopy(postcondition),
            "regression_argv": copy.deepcopy(regression),
        },
        "verification_commands": [
            *copy.deepcopy(postcondition),
            *copy.deepcopy(regression),
        ],
    }


def solution_context_identity_sha256(
    *,
    contract_sha256: str,
    contract: dict[str, Any],
    source_files: Iterable[SourceFileContext | dict[str, Any]],
) -> str:
    payload = solution_context_identity_payload(
        contract_sha256=contract_sha256,
        contract=contract,
        source_files=source_files,
    )
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SolutionContext:
    request_id: str | None
    contract_sha256: str
    repository: str
    source_commit: str
    source_tree: str
    allowed_paths: tuple[str, ...]
    protected_paths: tuple[str, ...]
    required_files: tuple[SourceFileContext, ...]
    success_criteria: dict[str, Any]
    verification_commands: tuple[tuple[str, ...], ...]
    source_observation_id: str
    source_observed_at: str

    @property
    def sha256(self) -> str:
        contract = {
            "request_id": self.request_id,
            "target": {
                "repository": self.repository,
                "commit": self.source_commit,
                "tree": self.source_tree,
            },
            "task": {
                "allowed_paths": list(self.allowed_paths),
                "protected_paths": list(self.protected_paths),
                "postcondition_argv": copy.deepcopy(self.success_criteria["postcondition_argv"]),
                "regression_argv": copy.deepcopy(self.success_criteria["regression_argv"]),
            },
        }
        return solution_context_identity_sha256(
            contract_sha256=self.contract_sha256,
            contract=contract,
            source_files=self.required_files,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "executor-solution-context/1.0",
            "request_id": self.request_id,
            "contract_sha256": self.contract_sha256,
            "repository": self.repository,
            "source_commit": self.source_commit,
            "source_tree": self.source_tree,
            "allowed_paths": list(self.allowed_paths),
            "protected_paths": list(self.protected_paths),
            "required_files": [item.to_dict() for item in self.required_files],
            "success_criteria": copy.deepcopy(self.success_criteria),
            "verification_commands": [list(item) for item in self.verification_commands],
            "source_observation_id": self.source_observation_id,
            "source_observed_at": self.source_observed_at,
            "solution_context_sha256": self.sha256,
        }


def build_solution_context(
    *,
    frozen_result: dict[str, Any],
    observation: Any,
) -> SolutionContext:
    if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
        raise SolutionContextError("solution context requires AUTHORIZED_AND_FROZEN")
    contract = frozen_result.get("contract")
    contract_sha256 = frozen_result.get("contract_sha256")
    if not isinstance(contract, dict) or not isinstance(contract_sha256, str):
        raise SolutionContextError("frozen contract identity is missing")
    target = contract.get("target")
    task = contract.get("task")
    if not isinstance(target, dict) or not isinstance(task, dict):
        raise SolutionContextError("frozen contract target/task is missing")
    if (
        observation.repository != target.get("repository")
        or observation.commit != target.get("commit")
        or observation.tree != target.get("tree")
    ):
        raise SolutionContextError("source observation differs from frozen target")

    observed_by_path = {item.path: item for item in observation.files}
    allowed = tuple(canonical_repository_path(path) for path in task["allowed_paths"])
    required: list[SourceFileContext] = []
    for path in allowed:
        item = observed_by_path.get(path)
        if item is None:
            raise SolutionContextError(f"source observation is missing allowed path: {path}")
        required.append(
            SourceFileContext(
                path=path,
                content=item.content,
                sha256=item.sha256,
                git_blob_sha=item.git_blob_sha,
            )
        )
    success = {
        "postcondition_argv": copy.deepcopy(task.get("postcondition_argv", [])),
        "regression_argv": copy.deepcopy(task.get("regression_argv", [])),
    }
    commands = tuple(
        tuple(item)
        for item in [*success["postcondition_argv"], *success["regression_argv"]]
    )
    context = SolutionContext(
        request_id=contract.get("request_id"),
        contract_sha256=contract_sha256,
        repository=target["repository"],
        source_commit=target["commit"],
        source_tree=target["tree"],
        allowed_paths=allowed,
        protected_paths=tuple(task.get("protected_paths", [])),
        required_files=tuple(required),
        success_criteria=success,
        verification_commands=commands,
        source_observation_id=observation.observation_id,
        source_observed_at=observation.observed_at,
    )
    # Force construction-time validation of the canonical identity payload.
    _ = context.sha256
    return context
