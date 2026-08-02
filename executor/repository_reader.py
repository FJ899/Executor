from __future__ import annotations

from pathlib import Path
from typing import Any

from executor.policy import wrap_repository_content
from executor.repository_access import canonical_repository_path
from executor.repository_identity import verify_repository_checkout
from executor.repository_snapshot import verify_worktree_file


def read_wrapped_repository_file(
    *,
    repository: str,
    commit: str,
    root: str | Path,
    path: str,
    project_contract: dict[str, Any],
) -> dict[str, Any]:
    verified_root = verify_repository_checkout(
        root,
        repository=repository,
        commit=commit,
        require_head=True,
    )
    canonical = canonical_repository_path(path)
    payload = verify_worktree_file(
        verified_root,
        commit=commit,
        path=canonical,
    )
    content = payload.decode("utf-8")
    return wrap_repository_content(
        repository=repository,
        commit=commit,
        path=canonical,
        content=content,
        project_contract=project_contract,
    )
