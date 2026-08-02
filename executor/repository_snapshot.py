from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

from executor.repository_access import RepositoryPathError, canonical_repository_path, read_repository_bytes


class RepositorySnapshotError(ValueError):
    pass


def _git_bytes(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RepositorySnapshotError(f"Cannot inspect committed repository data: {exc}") from exc


def read_commit_file(root: str | Path, *, commit: str, path: str) -> bytes:
    repository_root = Path(root)
    canonical = canonical_repository_path(path)
    completed = _git_bytes(repository_root, "show", f"{commit}:{canonical}")
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RepositorySnapshotError(f"Committed file is unavailable: {canonical}: {detail}")
    return completed.stdout


def verify_worktree_file(root: str | Path, *, commit: str, path: str) -> bytes:
    repository_root = Path(root)
    canonical, actual = read_repository_bytes(repository_root, path)
    committed = read_commit_file(repository_root, commit=commit, path=canonical)
    if actual != committed:
        raise RepositorySnapshotError(f"Working-tree file differs from committed blob: {canonical}")
    return actual


def _tracked_files(root: Path, *, commit: str, source_prefix: str) -> set[str]:
    completed = _git_bytes(root, "ls-tree", "-r", "-z", "--name-only", commit, "--", source_prefix)
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RepositorySnapshotError(f"Cannot enumerate committed source tree: {detail}")
    try:
        names = {item.decode("utf-8") for item in completed.stdout.split(b"\0") if item}
    except UnicodeError as exc:
        raise RepositorySnapshotError(f"Committed source path is not UTF-8: {exc}") from exc
    return {canonical_repository_path(name) for name in names}


def verify_source_tree(root: str | Path, *, commit: str, source_dir: str | Path) -> tuple[str, ...]:
    repository_root = Path(root).resolve(strict=True)
    source = Path(source_dir).resolve(strict=True)
    try:
        relative_source = source.relative_to(repository_root)
    except ValueError as exc:
        raise RepositorySnapshotError("Source tree escapes repository root") from exc
    source_prefix = relative_source.as_posix()
    if source_prefix in {"", "."}:
        source_prefix = "."
    else:
        canonical_repository_path(source_prefix)

    committed = _tracked_files(repository_root, commit=commit, source_prefix=source_prefix)
    actual: set[str] = set()
    for current_value, directory_names, file_names in os.walk(source, topdown=True, followlinks=False):
        current = Path(current_value)
        if current == repository_root and ".git" in directory_names:
            directory_names.remove(".git")
        for directory_name in list(directory_names):
            candidate = current / directory_name
            if candidate.is_symlink():
                raise RepositorySnapshotError(f"Source tree contains symlink directory: {candidate}")
        for file_name in file_names:
            if current == repository_root and file_name == ".git":
                continue
            candidate = current / file_name
            if candidate.is_symlink():
                raise RepositorySnapshotError(f"Source tree contains symlink file: {candidate}")
            try:
                file_stat = candidate.stat()
            except OSError as exc:
                raise RepositorySnapshotError(f"Cannot inspect source file {candidate}: {exc}") from exc
            if not stat.S_ISREG(file_stat.st_mode):
                raise RepositorySnapshotError(f"Source tree contains non-regular file: {candidate}")
            if file_stat.st_nlink != 1:
                raise RepositorySnapshotError(f"Source tree contains hard-linked file: {candidate}")
            relative = canonical_repository_path(candidate.relative_to(repository_root).as_posix())
            actual.add(relative)

    missing = sorted(committed - actual)
    additional = sorted(actual - committed)
    if missing or additional:
        raise RepositorySnapshotError(f"Source tree differs from commit; missing={missing}, additional={additional}")
    if not committed:
        raise RepositorySnapshotError("Committed source tree contains no files")
    for path in sorted(committed):
        try:
            verify_worktree_file(repository_root, commit=commit, path=path)
        except RepositoryPathError as exc:
            raise RepositorySnapshotError(str(exc)) from exc
    return tuple(sorted(committed))
