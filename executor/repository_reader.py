from __future__ import annotations

from pathlib import Path
from typing import Any

from executor.policy import wrap_repository_content
from executor.repository_access import read_repository_text
from executor.repository_identity import verify_repository_checkout


def read_wrapped_repository_file(
    *,
    repository: str,
    commit: str,
    root: str | Path,
    path: str,
    project_contract: dict[str, Any],
) -> dict[str, Any]:
    verified_root = verify_repository_checkout(root, repository=repository, commit=commit, require_head=True)
    canonical, content = read_repository_text(verified_root, path)
    return wrap_repository_content(
        repository=repository,
        commit=commit,
        path=canonical,
        content=content,
        project_contract=project_contract,
    )
