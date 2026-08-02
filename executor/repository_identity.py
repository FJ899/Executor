from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse


class RepositoryIdentityError(ValueError):
    pass


def repository_identity_from_remote(remote: str) -> tuple[str, str] | None:
    value = remote.strip()
    host: str | None
    path: str
    if value.startswith("git@") and ":" in value:
        authority, path = value.split(":", 1)
        host = authority.split("@", 1)[1]
    else:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.hostname:
            return None
        host = parsed.hostname
        path = parsed.path
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) < 2:
        return None
    return host.lower(), "/".join(parts[-2:])


def repository_name_from_remote(remote: str) -> str | None:
    identity = repository_identity_from_remote(remote)
    return identity[1] if identity is not None else None


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


def verify_repository_checkout(
    root_value: str | Path,
    *,
    repository: str,
    commit: str,
    require_head: bool = True,
    expected_host: str = "github.com",
) -> Path:
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
    identity = repository_identity_from_remote(remote_result.stdout)
    if identity is None:
        raise RepositoryIdentityError("Repository origin is not a supported hosted Git remote")
    actual_host, actual_repository = identity
    if actual_host != expected_host.lower():
        raise RepositoryIdentityError(f"Repository host is {actual_host}, expected {expected_host}")
    if actual_repository.lower() != repository.lower():
        raise RepositoryIdentityError(f"Repository root resolves to {actual_repository}, expected {repository}")

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
