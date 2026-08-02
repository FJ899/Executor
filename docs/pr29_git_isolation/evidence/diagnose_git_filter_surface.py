#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

COMMANDS = (
    "status",
    "rev-parse",
    "remote",
    "cat-file",
    "ls-tree",
    "worktree-add",
    "switch",
    "diff",
    "add",
    "commit",
)
FILTERS = ("clean", "smudge", "process")


def run_git(
    root: Path,
    *args: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        "git",
        "-C",
        str(root),
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.attributesFile=/dev/null",
        "-c",
        "core.autocrlf=false",
        "-c",
        "commit.gpgSign=false",
        *args,
    ]
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        env=env,
        timeout=15,
    )


def setup_case(base: Path, filter_kind: str) -> tuple[Path, Path, dict[str, str]]:
    source = base / "source"
    source.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.name", "tester"],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "config",
            "user.email",
            "tester@example.invalid",
        ],
        check=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "remote",
            "add",
            "origin",
            "https://github.com/example/repo.git",
        ],
        check=True,
    )
    (source / "project_registry").mkdir()
    target = source / "project_registry/registry.py"
    target.write_text("BROKEN\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(source), "add", "project_registry/registry.py"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(source), "commit", "-qm", "initial"],
        check=True,
    )

    marker = base / "marker"
    program = base / "filter.sh"
    if filter_kind == "process":
        program.write_text(
            "#!/bin/sh\nprintf process >> \"$FILTER_MARKER\"\nexit 1\n",
            encoding="utf-8",
        )
    else:
        program.write_text(
            f"#!/bin/sh\nprintf {filter_kind} >> \"$FILTER_MARKER\"\ncat\n",
            encoding="utf-8",
        )
    program.chmod(0o755)
    (source / ".git/info/attributes").write_text(
        "project_registry/registry.py filter=hostexec\n",
        encoding="utf-8",
    )
    if filter_kind == "clean":
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "config",
                "filter.hostexec.clean",
                str(program),
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "config",
                "filter.hostexec.smudge",
                "cat",
            ],
            check=True,
        )
    elif filter_kind == "smudge":
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "config",
                "filter.hostexec.clean",
                "cat",
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "config",
                "filter.hostexec.smudge",
                str(program),
            ],
            check=True,
        )
    else:
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "config",
                "filter.hostexec.process",
                str(program),
            ],
            check=True,
        )

    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        FILTER_MARKER=str(marker),
    )
    return source, marker, env


def execute_one(
    source: Path,
    marker: Path,
    env: dict[str, str],
    command_name: str,
) -> subprocess.CompletedProcess[str]:
    marker.unlink(missing_ok=True)
    if command_name == "status":
        return run_git(source, "status", "--porcelain", "--untracked-files=all", env=env)
    if command_name == "rev-parse":
        return run_git(source, "rev-parse", "HEAD", env=env)
    if command_name == "remote":
        return run_git(source, "remote", "get-url", "origin", env=env)
    if command_name == "cat-file":
        return run_git(source, "cat-file", "-e", "HEAD^{commit}", env=env)
    if command_name == "ls-tree":
        return run_git(source, "ls-tree", "-r", "--name-only", "HEAD", env=env)
    if command_name == "worktree-add":
        return run_git(
            source,
            "worktree",
            "add",
            "--detach",
            str(source.parent / "worktree"),
            "HEAD",
            env=env,
        )
    if command_name == "switch":
        return run_git(source, "switch", "-c", "diagnostic-branch", env=env)
    if command_name == "diff":
        return run_git(
            source,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--name-only",
            env=env,
        )
    if command_name == "add":
        (source / "project_registry/registry.py").write_text(
            "FIXED\n",
            encoding="utf-8",
        )
        marker.unlink(missing_ok=True)
        return run_git(source, "add", "--", "project_registry/registry.py", env=env)
    if command_name == "commit":
        (source / "project_registry/registry.py").write_text(
            "FIXED\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "-C", str(source), "add", "project_registry/registry.py"],
            check=False,
            env=env,
            capture_output=True,
        )
        marker.unlink(missing_ok=True)
        return run_git(
            source,
            "-c",
            "user.name=diagnostic",
            "-c",
            "user.email=diagnostic@example.invalid",
            "commit",
            "-m",
            "diagnostic",
            env=env,
        )
    raise AssertionError(command_name)


def main() -> None:
    print(f"git_version={subprocess.check_output(['git', '--version'], text=True).strip()}")
    print("filter,command,executed,returncode")
    for filter_kind in FILTERS:
        for command_name in COMMANDS:
            with tempfile.TemporaryDirectory(
                prefix="executor-git-surface-"
            ) as temp_name:
                base = Path(temp_name)
                source, marker, env = setup_case(base, filter_kind)
                try:
                    result = execute_one(source, marker, env, command_name)
                except subprocess.TimeoutExpired:
                    print(f"{filter_kind},{command_name},TIMEOUT,124")
                    continue
                executed = marker.exists() and bool(
                    marker.read_text(encoding="utf-8")
                )
                print(
                    f"{filter_kind},{command_name},"
                    f"{'YES' if executed else 'NO'},{result.returncode}"
                )
                shutil.rmtree(base / "worktree", ignore_errors=True)


if __name__ == "__main__":
    main()
