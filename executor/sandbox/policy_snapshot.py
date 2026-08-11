from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, verify_worktree_file
from executor.strict_json import StrictJsonError, loads_json_object


class ExecutionPolicyError(ValueError):
    pass


_POLICY_SNAPSHOT_PROOF = object()
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_COMMIT = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")


@dataclass(frozen=True)
class ControlledExternalFixture:
    task: str
    repository: str
    commit: str

    def matches(self, *, task: str, repository: str, commit: str) -> bool:
        return (
            self.task == task
            and self.repository == repository
            and self.commit == commit.lower()
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "task": self.task,
            "repository": self.repository,
            "commit": self.commit,
        }


@dataclass(frozen=True, init=False)
class ExecutionPolicySnapshot:
    repository: str
    commit: str
    repository_root: Path
    source_path: str
    source_sha256: str
    external_projects: bool
    controlled_external_fixtures: tuple[ControlledExternalFixture, ...]
    auto_merge: bool
    default_network: bool
    default_secrets: tuple[str, ...]

    def __init__(
        self,
        *,
        repository: str,
        commit: str,
        repository_root: Path,
        source_path: str,
        source_sha256: str,
        external_projects: bool,
        controlled_external_fixtures: tuple[ControlledExternalFixture, ...] = (),
        auto_merge: bool,
        default_network: bool,
        default_secrets: tuple[str, ...],
        _proof: object | None = None,
    ) -> None:
        if _proof is not _POLICY_SNAPSHOT_PROOF:
            raise ExecutionPolicyError(
                "ExecutionPolicySnapshot must be created from a verified policy file"
            )
        object.__setattr__(self, "repository", repository)
        object.__setattr__(self, "commit", commit)
        object.__setattr__(self, "repository_root", repository_root)
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "source_sha256", source_sha256)
        object.__setattr__(self, "external_projects", external_projects)
        object.__setattr__(self, "controlled_external_fixtures", controlled_external_fixtures)
        object.__setattr__(self, "auto_merge", auto_merge)
        object.__setattr__(self, "default_network", default_network)
        object.__setattr__(self, "default_secrets", default_secrets)

    def authorizes_controlled_external_fixture(
        self,
        *,
        task: str,
        repository: str,
        commit: str,
    ) -> bool:
        if self.external_projects:
            return False
        normalized_commit = commit.lower()
        return any(
            fixture.matches(
                task=task,
                repository=repository,
                commit=normalized_commit,
            )
            for fixture in self.controlled_external_fixtures
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "commit": self.commit,
            "repository_root": str(self.repository_root),
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "execution": {
                "external_projects": self.external_projects,
                "controlled_external_fixtures": [
                    fixture.to_dict() for fixture in self.controlled_external_fixtures
                ],
                "auto_merge": self.auto_merge,
                "default_network": self.default_network,
                "default_secrets": list(self.default_secrets),
            },
        }


def _parse_controlled_external_fixtures(value: object) -> tuple[ControlledExternalFixture, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ExecutionPolicyError(
            "execution.controlled_external_fixtures must be a list"
        )

    fixtures: list[ControlledExternalFixture] = []
    seen: set[tuple[str, str, str]] = set()
    for index, item in enumerate(value):
        path = f"execution.controlled_external_fixtures[{index}]"
        if not isinstance(item, dict):
            raise ExecutionPolicyError(f"{path} must be an object")
        expected = {"task", "repository", "commit"}
        if set(item) != expected:
            raise ExecutionPolicyError(
                f"{path} must contain exactly task, repository and commit"
            )
        task = item.get("task")
        repository = item.get("repository")
        commit = item.get("commit")
        if not isinstance(task, str) or not task:
            raise ExecutionPolicyError(f"{path}.task must be a non-empty string")
        if not isinstance(repository, str) or _REPOSITORY.fullmatch(repository) is None:
            raise ExecutionPolicyError(
                f"{path}.repository must use owner/name form"
            )
        if (
            not isinstance(commit, str)
            or _COMMIT.fullmatch(commit) is None
            or set(commit.lower()) == {"0"}
        ):
            raise ExecutionPolicyError(f"{path}.commit must be a concrete commit hash")
        key = (task, repository, commit.lower())
        if key in seen:
            raise ExecutionPolicyError(f"{path} duplicates an existing fixture binding")
        seen.add(key)
        fixtures.append(
            ControlledExternalFixture(
                task=task,
                repository=repository,
                commit=commit.lower(),
            )
        )
    return tuple(fixtures)


def load_execution_policy_snapshot(
    repository_root: str | Path,
    *,
    commit: str,
    repository: str = "JTJ07/Executor",
) -> ExecutionPolicySnapshot:
    try:
        root = verify_repository_checkout(
            repository_root,
            repository=repository,
            commit=commit,
            require_head=True,
        )
        payload = verify_worktree_file(
            root,
            commit=commit,
            path="EXECUTOR_POLICY.yaml",
        )
        document = loads_json_object(payload.decode("utf-8"))
    except (
        RepositoryIdentityError,
        RepositorySnapshotError,
        StrictJsonError,
        UnicodeError,
    ) as exc:
        raise ExecutionPolicyError(
            f"Cannot load authoritative executor policy: {exc}"
        ) from exc

    if document.get("schema_version") != "executor-policy/1.0":
        raise ExecutionPolicyError("EXECUTOR_POLICY.yaml must use executor-policy/1.0")
    execution = document.get("execution")
    if not isinstance(execution, dict):
        raise ExecutionPolicyError("EXECUTOR_POLICY.yaml requires execution policy")
    for key in ("external_projects", "auto_merge", "default_network"):
        if not isinstance(execution.get(key), bool):
            raise ExecutionPolicyError(f"execution.{key} must be boolean")
    secrets = execution.get("default_secrets")
    if not isinstance(secrets, list) or not all(
        isinstance(item, str) and item for item in secrets
    ):
        raise ExecutionPolicyError(
            "execution.default_secrets must be a list of non-empty names"
        )
    fixtures = _parse_controlled_external_fixtures(
        execution.get("controlled_external_fixtures")
    )

    return ExecutionPolicySnapshot(
        repository=repository,
        commit=commit,
        repository_root=root,
        source_path="EXECUTOR_POLICY.yaml",
        source_sha256=hashlib.sha256(payload).hexdigest(),
        external_projects=execution["external_projects"],
        controlled_external_fixtures=fixtures,
        auto_merge=execution["auto_merge"],
        default_network=execution["default_network"],
        default_secrets=tuple(secrets),
        _proof=_POLICY_SNAPSHOT_PROOF,
    )
