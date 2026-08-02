from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, verify_worktree_file
from executor.strict_json import StrictJsonError, loads_json_object


class ExecutionPolicyError(ValueError):
    pass


_POLICY_SNAPSHOT_PROOF = object()


@dataclass(frozen=True, init=False)
class ExecutionPolicySnapshot:
    repository: str
    commit: str
    repository_root: Path
    source_path: str
    source_sha256: str
    external_projects: bool
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
        object.__setattr__(self, "auto_merge", auto_merge)
        object.__setattr__(self, "default_network", default_network)
        object.__setattr__(self, "default_secrets", default_secrets)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "commit": self.commit,
            "repository_root": str(self.repository_root),
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "execution": {
                "external_projects": self.external_projects,
                "auto_merge": self.auto_merge,
                "default_network": self.default_network,
                "default_secrets": list(self.default_secrets),
            },
        }


def load_execution_policy_snapshot(
    repository_root: str | Path,
    *,
    commit: str,
    repository: str = "litrgratis-pixel/Executor",
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

    return ExecutionPolicySnapshot(
        repository=repository,
        commit=commit,
        repository_root=root,
        source_path="EXECUTOR_POLICY.yaml",
        source_sha256=hashlib.sha256(payload).hexdigest(),
        external_projects=execution["external_projects"],
        auto_merge=execution["auto_merge"],
        default_network=execution["default_network"],
        default_secrets=tuple(secrets),
        _proof=_POLICY_SNAPSHOT_PROOF,
    )
