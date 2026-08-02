from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse


class RepositoryIdentityError(ValueError):
    pass


def repository_name_from_remote(remote: str) -> str | None:
    value = remote.strip()
    if value.startswith("git@") and ":" in value:
        value = value.split(":", 1)[1]
    else:
        parsed = urlparse(value)
        if parsed.scheme:
            value = parsed.path
    value = value.strip("/")
    if value.endswith(".git"):
        value = value[:-4]
    parts = value.split("/")
    if len(parts) < 2:
        return None
    return "/".join(parts[-2:])


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RepositoryIdentityError(f"Cannot inspect repository: {exc}") from exc


def verify_repository_checkout(root_value: str | Path, *, repository: str, commit: str, require_head: bool = True) -> Path:
    root_input = Path(root_value)
    if root_input.is_symlink():
        raise RepositoryIdentityError("Repository root cannot be a symlink")
    try:
        root = root_input.resolve(strict=True)
    except OSError as exc:
        raise RepositoryIdentityError(f"Cannot resolve repository root: {exc}") from exc
    if not root.is_dir():
        raise RepositoryIdentityError("Repository root must be a directory")

    remote_result = _git(root, "remote", "get-url", "origin")
    if remote_result.returncode != 0:
        raise RepositoryIdentityError("Repository origin cannot be read")
    actual_repository = repository_name_from_remote(remote_result.stdout)
    if actual_repository is None or actual_repository.lower() != repository.lower():
        raise RepositoryIdentityError(f"Repository root resolves to {actual_repository or '<unknown>'}, expected {repository}")

    commit_result = _git(root, "cat-file", "-e", f"{commit}^{{commit}}")
    if commit_result.returncode != 0:
        raise RepositoryIdentityError(f"Commit is not present in repository: {commit}")
    if require_head:
        head_result = _git(root, "rev-parse", "HEAD")
        if head_result.returncode != 0:
            raise RepositoryIdentityError("Repository HEAD cannot be read")
        actual_head = head_result.stdout.strip()
        if actual_head.lower() != commit.lower():
            raise RepositoryIdentityError(f"Repository HEAD is {actual_head}, expected {commit}")
    return root
