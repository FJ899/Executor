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


def _root(root_value: str | Path) -> Path:
    root_input = Path(root_value)
    if root_input.is_symlink():
        raise RepositoryPathError("Repository root cannot be a symlink")
    try:
        root = root_input.resolve(strict=True)
    except OSError as exc:
        raise RepositoryPathError(f"Cannot resolve repository root: {exc}") from exc
    if not root.is_dir():
        raise RepositoryPathError("Repository root must be a directory")
    return root


def validate_repository_candidate(root_value: str | Path, relative: str) -> tuple[str, Path]:
    canonical = canonical_repository_path(relative)
    root = _root(root_value)
    parts = PurePosixPath(canonical).parts
    current = root
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            raise RepositoryPathError(f"Repository path contains symlink component: {part}")
        try:
            current = current.resolve(strict=True)
        except OSError as exc:
            raise RepositoryPathError(f"Repository parent cannot be resolved: {exc}") from exc
        try:
            current.relative_to(root)
        except ValueError as exc:
            raise RepositoryPathError("Repository path escapes repository root") from exc
        if not current.is_dir():
            raise RepositoryPathError("Repository path parent must be a directory")
    candidate = current / parts[-1]
    if candidate.is_symlink():
        raise RepositoryPathError(f"Repository path contains symlink component: {parts[-1]}")
    return canonical, candidate


def _read_resolved_bytes(resolved: Path) -> bytes:
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
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            content = stream.read()
        after_stat = os.fstat(descriptor)
        if (file_stat.st_dev, file_stat.st_ino, file_stat.st_size, file_stat.st_mtime_ns) != (
            after_stat.st_dev,
            after_stat.st_ino,
            after_stat.st_size,
            after_stat.st_mtime_ns,
        ):
            raise RepositoryPathError("Repository file changed during read")
    finally:
        os.close(descriptor)
    return content


class _VerifiedPath(type(Path())):
    def read_bytes(self) -> bytes:
        return _read_resolved_bytes(self)

    def read_text(self, encoding: str | None = None, errors: str | None = None) -> str:
        selected_encoding = encoding or "utf-8"
        try:
            return self.read_bytes().decode(selected_encoding, errors or "strict")
        except UnicodeError as exc:
            raise RepositoryPathError(f"Repository file must use {selected_encoding}: {exc}") from exc


def resolve_repository_file(root_value: str | Path, relative: str) -> tuple[str, Path]:
    canonical, candidate = validate_repository_candidate(root_value, relative)
    root = _root(root_value)
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
    return canonical, _VerifiedPath(resolved)


def read_repository_bytes(root_value: str | Path, relative: str) -> tuple[str, bytes]:
    canonical, resolved = resolve_repository_file(root_value, relative)
    return canonical, resolved.read_bytes()


def read_repository_text(root_value: str | Path, relative: str) -> tuple[str, str]:
    canonical, resolved = resolve_repository_file(root_value, relative)
    return canonical, resolved.read_text(encoding="utf-8")
