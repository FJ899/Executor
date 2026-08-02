from __future__ import annotations

import os
import stat
import unicodedata
from pathlib import Path, PurePosixPath


class RepositoryPathError(ValueError):
    pass


def canonical_repository_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise RepositoryPathError("Repository path must be non-empty text")
    if "\x00" in value:
        raise RepositoryPathError("Repository path cannot contain NUL")
    if "\\" in value:
        raise RepositoryPathError("Repository paths must use POSIX separators")
    if unicodedata.normalize("NFKC", value) != value:
        raise RepositoryPathError("Repository path must use stable normalized characters")
    path = PurePosixPath(value)
    if path.is_absolute() or value.startswith("/"):
        raise RepositoryPathError("Repository path must be relative")
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        raise RepositoryPathError("Drive-qualified paths are forbidden")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise RepositoryPathError("Repository path cannot contain empty, dot or parent segments")
    canonical = path.as_posix()
    if canonical in {"", "."}:
        raise RepositoryPathError("Repository path must identify a file")
    return canonical


def validate_scope_pattern(pattern: str) -> str:
    if not isinstance(pattern, str) or not pattern:
        raise RepositoryPathError("Scope pattern must be non-empty")
    if "\\" in pattern or pattern.startswith("/"):
        raise RepositoryPathError("Scope patterns must be relative POSIX globs")
    if unicodedata.normalize("NFKC", pattern) != pattern:
        raise RepositoryPathError("Scope pattern must use stable normalized characters")
    if any(part in {"", ".", ".."} for part in pattern.split("/")):
        raise RepositoryPathError("Scope pattern cannot contain empty, dot or parent segments")
    return pattern


def resolve_repository_file(root_value: str | Path, relative: str) -> tuple[str, Path]:
    canonical = canonical_repository_path(relative)
    root_input = Path(root_value)
    if root_input.is_symlink():
        raise RepositoryPathError("Repository root cannot be a symlink")
    try:
        root = root_input.resolve(strict=True)
    except OSError as exc:
        raise RepositoryPathError(f"Cannot resolve repository root: {exc}") from exc
    if not root.is_dir():
        raise RepositoryPathError("Repository root must be a directory")

    candidate = root
    for part in PurePosixPath(canonical).parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise RepositoryPathError(f"Repository path contains symlink component: {part}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise RepositoryPathError(f"Repository file cannot be resolved: {exc}") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RepositoryPathError("Repository file escapes repository root") from exc
    try:
        file_stat = resolved.stat()
    except OSError as exc:
        raise RepositoryPathError(f"Repository file cannot be inspected: {exc}") from exc
    if not stat.S_ISREG(file_stat.st_mode):
        raise RepositoryPathError("Repository path must identify a regular file")
    if file_stat.st_nlink != 1:
        raise RepositoryPathError("Repository file must not be hard-linked")
    return canonical, resolved


def read_repository_text(root_value: str | Path, relative: str) -> tuple[str, str]:
    canonical, resolved = resolve_repository_file(root_value, relative)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(resolved, flags)
    except OSError as exc:
        raise RepositoryPathError(f"Repository file cannot be opened safely: {exc}") from exc
    try:
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or file_stat.st_nlink != 1:
            raise RepositoryPathError("Repository file changed type or link count during read")
        with os.fdopen(descriptor, "r", encoding="utf-8", closefd=False) as stream:
            content = stream.read()
    except UnicodeError as exc:
        raise RepositoryPathError(f"Repository file must be UTF-8 text: {exc}") from exc
    finally:
        os.close(descriptor)
    return canonical, content
