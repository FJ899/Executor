from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from executor.repository_access import canonical_repository_path
from executor.repository_identity import RepositoryIdentityError, verify_repository_checkout
from executor.repository_snapshot import RepositorySnapshotError, read_commit_file
from executor.solution_context import source_observation_identity_sha256


class SolutionSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ObservedSourceFile:
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


@dataclass(frozen=True)
class SourceObservation:
    repository: str
    commit: str
    tree: str
    files: tuple[ObservedSourceFile, ...]
    observed_at: str
    observation_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "executor-solution-source-observation/1.0",
            "repository": self.repository,
            "commit": self.commit,
            "tree": self.tree,
            "files": [item.identity_dict() for item in self.files],
            "observed_at": self.observed_at,
            "observation_id": self.observation_id,
            "write_capability": "NONE",
        }


class SolutionSourceResolver(Protocol):
    def observe(
        self,
        *,
        frozen_result: dict[str, Any],
        source_root: str | Path,
    ) -> SourceObservation:
        ...


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_text(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SolutionSourceError(f"cannot inspect source repository: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise SolutionSourceError(f"git {' '.join(args)} failed: {detail}")
    return completed.stdout.strip()


@dataclass(frozen=True)
class GitSolutionSourceResolver:
    """Read-only resolver for the exact frozen source checkout.

    The resolver accepts a local checkout that must already be positioned at the
    frozen commit. It reads committed blobs through Git; it never mutates the
    repository, creates refs, or calls any publication API.
    """

    def observe(
        self,
        *,
        frozen_result: dict[str, Any],
        source_root: str | Path,
    ) -> SourceObservation:
        if frozen_result.get("status") != "AUTHORIZED_AND_FROZEN":
            raise SolutionSourceError("source observation requires AUTHORIZED_AND_FROZEN")
        contract = frozen_result.get("contract")
        if not isinstance(contract, dict):
            raise SolutionSourceError("frozen contract is missing")
        target = contract.get("target")
        task = contract.get("task")
        if not isinstance(target, dict) or not isinstance(task, dict):
            raise SolutionSourceError("frozen target/task is missing")
        repository = target.get("repository")
        commit = target.get("commit")
        tree = target.get("tree")
        if not all(isinstance(item, str) and item for item in (repository, commit, tree)):
            raise SolutionSourceError("frozen repository/commit/tree identity is incomplete")
        allowed = task.get("allowed_paths")
        if not isinstance(allowed, list) or not allowed:
            raise SolutionSourceError("frozen allowed_paths are missing")

        try:
            root = verify_repository_checkout(
                source_root,
                repository=repository,
                commit=commit,
                require_head=True,
            )
        except RepositoryIdentityError as exc:
            raise SolutionSourceError(f"source checkout identity mismatch: {exc}") from exc

        actual_tree = _git_text(root, "rev-parse", "HEAD^{tree}")
        if actual_tree != tree:
            raise SolutionSourceError(
                f"source checkout tree is {actual_tree}, expected {tree}"
            )
        if _git_text(root, "status", "--porcelain=v1", "--untracked-files=all"):
            raise SolutionSourceError("source checkout must be clean")

        files: list[ObservedSourceFile] = []
        for raw_path in allowed:
            try:
                path = canonical_repository_path(raw_path)
            except (TypeError, ValueError) as exc:
                raise SolutionSourceError("frozen allowed path is invalid") from exc
            try:
                payload = read_commit_file(root, commit=commit, path=path)
            except RepositorySnapshotError as exc:
                raise SolutionSourceError(f"cannot read frozen source path {path}: {exc}") from exc
            try:
                content = payload.decode("utf-8")
            except UnicodeError as exc:
                raise SolutionSourceError(f"solution source file is not UTF-8 text: {path}") from exc
            blob_sha = _git_text(root, "rev-parse", f"{commit}:{path}")
            if _git_text(root, "cat-file", "-t", blob_sha) != "blob":
                raise SolutionSourceError(f"source path is not a Git blob: {path}")
            files.append(
                ObservedSourceFile(
                    path=path,
                    content=content,
                    sha256=hashlib.sha256(payload).hexdigest(),
                    git_blob_sha=blob_sha,
                )
            )

        observation_id = source_observation_identity_sha256(
            repository=repository,
            commit=commit,
            tree=tree,
            source_files=files,
        )
        return SourceObservation(
            repository=repository,
            commit=commit,
            tree=tree,
            files=tuple(files),
            observed_at=_utc_now(),
            observation_id=observation_id,
        )
