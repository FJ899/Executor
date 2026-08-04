from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_URL = "https://github.com/litrgratis-pixel/executor-pilot-target.git"
GIT_IMAGE_REF = "alpine/git@sha256:0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd"
SANDBOX_IMAGE_REF = "python@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba"
BROKER_AUTHORITY = "TRUSTED_HOST_HARNESS"
BROKER_ENDPOINT = "UNIX_COMMAND_BROKER_ONLY"
BROKER_CLASSES = {
    "version", "image-inspect", "run-git-network", "run-git-offline",
    "create-sandbox", "ps-container", "inspect-container", "start-container",
    "kill-container", "wait-container", "remove-container",
    "broker-owned-acquisition",
}
KNOWN_RUNTIMES = {"runc", "io.containerd.runc.v2"}
CASE_IDS = {"001", "002", "003"}
CASE_RE = re.compile(r"(?:^|/)case-(00[1-3])(?:/|$)")
FULL_OID_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_PATH_RE = re.compile(
    r"^/(?:runs|candidate)/[A-Za-z0-9][A-Za-z0-9_.-]*(?:/[A-Za-z0-9_.-]+)*$"
)
BRANCH_RE = re.compile(r"^executor/case-00[1-3]-[0-9a-f]{12}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ALLOWED_CONFIG = {
    "core.hooksPath": "/dev/null",
    "core.fsmonitor": "false",
    "core.autocrlf": "false",
    "core.safecrlf": "true",
    "core.attributesFile": "/dev/null",
    "commit.gpgSign": "false",
    "tag.gpgSign": "false",
    "credential.helper": "",
    "core.askPass": "/bin/false",
    "diff.external": "",
    "interactive.diffFilter": "",
    "fetch.recurseSubmodules": "false",
    "submodule.recurse": "false",
    "http.followRedirects": "false",
    "user.name": "Creative OS Executor",
    "user.email": "executor@localhost",
}
FETCH_CONFIG = [
    "-c", "credential.helper=",
    "-c", "core.askPass=/bin/false",
    "-c", "http.followRedirects=false",
    "-c", "http.proxy=",
    "-c", "http.extraHeader=",
    "-c", "http.sslVerify=true",
    "-c", "protocol.allow=never",
    "-c", "protocol.https.allow=always",
    "-c", "protocol.file.allow=never",
    "-c", "protocol.ext.allow=never",
    "-c", "protocol.ssh.allow=never",
    "-c", "protocol.git.allow=never",
]
WORKTREE_FILTER_CONFIG = [
    "-c", "filter.lfs.process=",
    "-c", "filter.lfs.smudge=cat",
    "-c", "filter.lfs.clean=cat",
    "-c", "filter.lfs.required=false",
]
GIT_ENVIRONMENT = [
    "HOME=/executor-run/isolated-home",
    "XDG_CONFIG_HOME=/executor-run/isolated-xdg",
    "GIT_CONFIG_NOSYSTEM=1",
    "GIT_CONFIG_GLOBAL=/dev/null",
    "GIT_ATTR_NOSYSTEM=1",
    "GIT_TERMINAL_PROMPT=0",
    "GIT_ASKPASS=/bin/false",
    "SSH_ASKPASS=/bin/false",
    "GIT_SSH_COMMAND=/bin/false",
    "GIT_LFS_SKIP_SMUDGE=1",
    "GIT_ALLOW_PROTOCOL=https",
    "GIT_PROTOCOL_FROM_USER=0",
    "GIT_CEILING_DIRECTORIES=/executor-run",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM=0",
    "GIT_PAGER=cat",
    "GIT_EDITOR=/bin/false",
    "PATH=/usr/bin:/bin",
    "LC_ALL=C",
    "LANG=C",
    "TZ=UTC",
]

def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()

def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode())

def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))

def _option(argv: list[str], name: str) -> list[str]:
    values: list[str] = []
    for index, item in enumerate(argv):
        if item == name and index + 1 < len(argv):
            values.append(argv[index + 1])
        elif item.startswith(name + "="):
            values.append(item.split("=", 1)[1])
    return values

def _option_count(argv: list[str], name: str) -> int:
    return sum(1 for item in argv if item == name or item.startswith(name + "="))

def _has_exact_flag(argv: list[str], name: str) -> bool:
    return argv.count(name) == 1 and not any(item.startswith(name + "=") for item in argv)


def _exact_option_grammar(
    argv: list[str], *, flags: set[str], value_options: set[str]
) -> tuple[bool, str]:
    if not argv:
        return False, "empty Docker command"
    index = 1
    while index < len(argv):
        token = argv[index]
        if token in flags:
            index += 1
            continue
        if token in value_options:
            if index + 1 >= len(argv):
                return False, f"missing value for {token}"
            index += 2
            continue
        if any(token.startswith(name + "=") for name in value_options):
            index += 1
            continue
        return False, f"unapproved Docker option or positional token before image: {token}"
    return True, ""


def _case_id_from_argv(argv: list[str]) -> str | None:
    for item in argv:
        match = CASE_RE.search(item)
        if match:
            return match.group(1)
    return None

def _has_forbidden_runtime_option(argv: list[str]) -> bool:
    forbidden_exact = {
        "-v", "--volume", "--env-file", "--add-host", "--privileged",
        "--device", "--device-cgroup-rule", "--cap-add", "--pid", "--ipc",
        "--uts", "--cgroupns", "--userns",
    }
    forbidden_prefixes = (
        "--volume=", "--env-file=", "--add-host=", "--privileged=",
        "--device=", "--device-cgroup-rule=", "--cap-add=", "--pid=",
        "--ipc=", "--uts=", "--cgroupns=", "--userns=",
    )
    return any(item in forbidden_exact or item.startswith(forbidden_prefixes) for item in argv)

def _parse_mount(value: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    for item in value.split(","):
        if "=" in item:
            key, content = item.split("=", 1)
            fields[key] = content
        else:
            fields[item] = True
    return fields

def _safe_mount(value: str, destination: str, *, readonly: bool) -> bool:
    fields = _parse_mount(value)
    source = fields.get("src") or fields.get("source")
    dest = fields.get("dst") or fields.get("destination")
    if fields.get("type") != "bind" or dest != destination or not isinstance(source, str):
        return False
    if ".." in Path(source).parts or RUN_PATH_RE.fullmatch(source) is None:
        return False
    if readonly and fields.get("readonly") is not True:
        return False
    if not readonly and fields.get("rw") is not True:
        return False
    return True

def _split_git_command(command: list[str]) -> list[str] | None:
    if len(command) < 4 or command[:2] != ["env", "-i"]:
        return None
    try:
        index = command.index("/usr/bin/git")
    except ValueError:
        return None
    if command[2:index] != GIT_ENVIRONMENT:
        return None
    return command[index + 1 :]

def _safe_executor_path(value: str) -> bool:
    return value.startswith("/executor-run/") and ".." not in Path(value).parts

def _offline_git_allowed(git_args: list[str]) -> bool:
    if git_args == ["--version"]:
        return True
    if any(
        item.startswith("alias.") or "!" in item
        or item in {"--config-env", "--exec-path", "--upload-pack"}
        for item in git_args
    ):
        return False
    if (
        len(git_args) == 3 and git_args[:2] == ["init", "--bare"]
        and _safe_executor_path(git_args[2])
    ):
        return True
    rest = list(git_args)
    if len(rest) >= 3 and rest[0] in {"--git-dir", "-C"}:
        if not _safe_executor_path(rest[1]):
            return False
        rest = rest[2:]
    if rest[:2] == ["config", "--local"] and len(rest) == 4:
        return ALLOWED_CONFIG.get(rest[2]) == rest[3]
    if rest and rest[0] in {
        "rev-parse", "fsck", "status", "add", "commit", "diff",
        "rev-list", "cat-file", "show", "switch",
    }:
        if any(
            item in {"-c", "--config-env", "--upload-pack", "--exec-path"}
            or item.startswith("alias.") or "!" in item or "://" in item
            for item in rest[1:]
        ):
            return False
        if rest[0] == "switch":
            return len(rest) == 3 and rest[1] == "-c" and BRANCH_RE.fullmatch(rest[2]) is not None
        return True
    if rest[:2] == ["worktree", "add"]:
        return (
            len(rest) == 5 and rest[2] == "--detach"
            and _safe_executor_path(rest[3])
            and FULL_OID_RE.fullmatch(rest[4]) is not None
        )
    if git_args[: len(WORKTREE_FILTER_CONFIG)] == WORKTREE_FILTER_CONFIG:
        return _offline_git_allowed(git_args[len(WORKTREE_FILTER_CONFIG) :])
    return False

def _network_git_allowed(git_args: list[str], canonical_url: str) -> bool:
    if git_args[: len(FETCH_CONFIG)] != FETCH_CONFIG:
        return False
    rest = git_args[len(FETCH_CONFIG) :]
    if len(rest) != 8 or rest[0] != "--git-dir" or not _safe_executor_path(rest[1]):
        return False
    if rest[2:7] != [
        "fetch", "--no-tags", "--no-recurse-submodules", "--depth=1", canonical_url
    ]:
        return False
    refspec = rest[7]
    return (
        refspec.startswith("+")
        and refspec.endswith(":refs/executor/input")
        and FULL_OID_RE.fullmatch(refspec[1:41]) is not None
        and refspec[41:] == ":refs/executor/input"
    )

def _baseline_classify_broker_argv(
    argv: object,
    *,
    git_image: str,
    sandbox_image_id: str,
    canonical_url: str,
    created: set[str],
) -> tuple[bool, str, str]:
    if (
        not isinstance(argv, list) or not argv
        or not all(
            isinstance(item, str) and item
            and not any(ord(character) < 32 for character in item)
            for item in argv
        )
    ):
        return False, "invalid", "invalid argv"
    if any(item in {"-H", "--host"} or item.startswith("--host=") for item in argv):
        return False, "raw-api", "raw Docker host selection forbidden"
    if argv[0] in {
        "pull", "build", "exec", "login", "push", "tag", "load", "save",
        "import", "export", "context", "system", "plugin", "network", "volume", "swarm",
    }:
        return False, "raw-api", f"forbidden Docker command: {argv[0]}"
    if argv == ["version", "--format", "{{.Server.Version}}"]:
        return True, "version", ""
    if (
        len(argv) == 5 and argv[:3] == ["image", "inspect", "--format"]
        and argv[4] == git_image
    ):
        return True, "image-inspect", ""
    if argv[0] == "run":
        if argv.count(git_image) != 1 or _has_forbidden_runtime_option(argv):
            return False, "run-git", "untrusted Git container shape"
        image_index = argv.index(git_image)
        before = argv[:image_index]
        command = argv[image_index + 1 :]
        network = _option(before, "--network")
        if len(network) != 1 or network[0] not in {"none", "bridge"}:
            return False, "run-git", "invalid network mode"
        if "--rm" not in before or _option(before, "--platform") != ["linux/amd64"]:
            return False, "run-git", "missing immutable Git runtime controls"
        if _option(before, "--entrypoint") != ["/bin/busybox"]:
            return False, "run-git", "Git entrypoint is not exact"
        mounts = _option(before, "--mount")
        if len(mounts) != 1 or not _safe_mount(mounts[0], "/executor-run", readonly=False):
            return False, "run-git", "Git mount outside isolated roots"
        git_args = _split_git_command(command)
        if git_args is None:
            return False, "run-git", "untrusted Git environment or binary"
        if network[0] == "bridge":
            if _network_git_allowed(git_args, canonical_url):
                return True, "run-git-network", ""
            return False, "run-git-network", "networked Git command is not exact pinned fetch"
        if _offline_git_allowed(git_args):
            return True, "run-git-offline", ""
        return False, "run-git-offline", "offline Git command is outside exact grammar"
    if argv[0] == "create":
        if argv.count(sandbox_image_id) != 1 or _has_forbidden_runtime_option(argv):
            return False, "create-sandbox", "untrusted sandbox container shape"
        image_index = argv.index(sandbox_image_id)
        before = argv[:image_index]
        command = argv[image_index + 1 :]
        names = _option(before, "--name")
        network = _option(before, "--network")
        mounts = _option(before, "--mount")
        if len(names) != 1 or NAME_RE.fullmatch(names[0]) is None:
            return False, "create-sandbox", "invalid sandbox name"
        if network != ["none"]:
            return False, "create-sandbox", "sandbox network must be none"
        if _option(before, "--entrypoint"):
            return False, "create-sandbox", "sandbox entrypoint override is forbidden"
        if _option(before, "--user") != ["65534:65534"] or _option(before, "--workdir") != ["/source"]:
            return False, "create-sandbox", "sandbox identity or workdir mismatch"
        if _option(before, "--pids-limit") not in (["16"], ["64"]):
            return False, "create-sandbox", "sandbox pids limit outside pilot bounds"
        if _option(before, "--memory") not in (["48m"], ["64m"], ["256m"]):
            return False, "create-sandbox", "sandbox memory outside pilot bounds"
        if _option(before, "--cpus") not in (["1"], ["1.0"]):
            return False, "create-sandbox", "sandbox cpu outside pilot bounds"
        if len(mounts) != 1 or not _safe_mount(mounts[0], "/source", readonly=True):
            return False, "create-sandbox", "sandbox mount outside isolated roots"
        allowed_commands = [
            ["python", "-m", "compileall", "-q", "project_registry", "tests"],
            ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
        ]
        fixture_actions = {
            "read_source", "write_source", "write_workspace", "network",
            "environment", "sleep", "pids", "memory", "disk",
        }
        fixture_command = (
            len(command) == 3 and command[:2] == ["python", "/source/sandbox_fixture.py"]
            and command[2] in fixture_actions
        )
        if command not in allowed_commands and not fixture_command:
            return False, "create-sandbox", "sandbox command outside pilot contract"
        return True, "create-sandbox", ""
    if argv[0] == "ps":
        filters = _option(argv, "--filter")
        formats = _option(argv, "--format")
        if argv[1:3] != ["-a", "--no-trunc"] or len(filters) != 1 or formats != ["{{.Names}}"]:
            return False, "ps-container", "invalid exact-name query"
        value = filters[0]
        if not (value.startswith("name=^/") and value.endswith("$")):
            return False, "ps-container", "non-exact container query"
        name = value[7:-1]
        if NAME_RE.fullmatch(name) is None:
            return False, "ps-container", "invalid container query name"
        return True, "ps-container", ""
    if argv[0] == "inspect":
        formats = _option(argv, "--format")
        target = argv[-1]
        if len(formats) != 1 or target not in created:
            return False, "inspect-container", "inspect target not broker-owned"
        return True, "inspect-container", ""
    if argv[0] in {"start", "kill", "wait", "rm"}:
        target = argv[-1]
        if target not in created:
            return False, f"{argv[0]}-container", "container target not broker-owned"
        exact = {
            "start": ["start", "-a", target],
            "kill": ["kill", target],
            "wait": ["wait", target],
            "rm": ["rm", "-f", target],
        }
        if argv != exact[argv[0]]:
            return False, f"{argv[0]}-container", "container command shape invalid"
        classes = {
            "start": "start-container", "kill": "kill-container",
            "wait": "wait-container", "rm": "remove-container",
        }
        return True, classes[argv[0]], ""
    return False, "unknown", f"unknown Docker command: {argv[0]}"

def _strict_runtime_controls(argv: list[str], *, command: str) -> tuple[bool, str]:
    if command not in {"run-git", "create-sandbox"}:
        return True, ""
    if command == "run-git":
        grammar_ok, grammar_reason = _exact_option_grammar(
            argv,
            flags={"--rm", "--read-only"},
            value_options={
                "--platform", "--network", "--cap-drop", "--security-opt",
                "--pids-limit", "--memory", "--cpus", "--user", "--tmpfs",
                "--workdir", "--mount", "--entrypoint",
            },
        )
    else:
        grammar_ok, grammar_reason = _exact_option_grammar(
            argv,
            flags={"--read-only"},
            value_options={
                "--name", "--network", "--cap-drop", "--security-opt",
                "--pids-limit", "--memory", "--cpus", "--user", "--env",
                "--workdir", "--mount", "--tmpfs",
            },
        )
    if not grammar_ok:
        return False, grammar_reason
    if not _has_exact_flag(argv, "--read-only"):
        return False, "read-only rootfs flag is missing, duplicated or contradicted"
    if _option_count(argv, "--runtime"):
        return False, "explicit runtime selection is forbidden"
    if _option(argv, "--cap-drop") != ["ALL"]:
        return False, "capability drop must be exactly ALL"
    if _option(argv, "--security-opt") != ["no-new-privileges"]:
        return False, "security option must be exactly no-new-privileges"

    if command == "run-git":
        singleton = (
            "--platform", "--network", "--pids-limit", "--memory", "--cpus",
            "--user", "--workdir", "--mount", "--entrypoint",
        )
        for name in singleton:
            if _option_count(argv, name) != 1:
                return False, f"{name} must occur exactly once"
        if _option(argv, "--user") != ["1000:1000"]:
            return False, "Git container user must be exactly 1000:1000"
        tmpfs = _option(argv, "--tmpfs")
        allowed_tmpfs = {
            "/tmp:rw,noexec,nosuid,size=64m",
            "/tmp:rw,nosuid,nodev,noexec,size=67108864",
        }
        if len(tmpfs) != 1 or tmpfs[0] not in allowed_tmpfs:
            return False, "Git tmpfs shape is not exact"
    else:
        singleton = (
            "--network", "--pids-limit", "--memory", "--cpus",
            "--user", "--workdir", "--mount",
        )
        for name in singleton:
            if _option_count(argv, name) != 1:
                return False, f"{name} must occur exactly once"
        if _option_count(argv, "--platform") or _option_count(argv, "--entrypoint"):
            return False, "sandbox platform and entrypoint overrides are forbidden"
        if _option(argv, "--user") != ["65534:65534"]:
            return False, "sandbox user must be exactly 65534:65534"
        if _option_count(argv, "--env") != 1 or _option(argv, "--env") != ["HOME=/nonexistent"]:
            return False, "sandbox environment must be exactly HOME=/nonexistent"
        tmpfs = _option(argv, "--tmpfs")
        expected = {
            "/workspace:rw,nosuid,nodev,size=8m,mode=1777",
            "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
        }
        if len(tmpfs) != 2 or set(tmpfs) != expected:
            return False, "sandbox tmpfs set is not exact"
    return True, ""

def _legacy_network_fetch_request(
    argv: object, *, git_image: str, canonical_url: str
) -> tuple[bool, str]:
    if not isinstance(argv, list):
        return False, "invalid argv"
    allowed, command_class, reason = _baseline_classify_broker_argv(
        argv,
        git_image=git_image,
        sandbox_image_id="<unused>",
        canonical_url=canonical_url,
        created=set(),
    )
    if not allowed or command_class != "run-git-network":
        return False, reason or "not an exact legacy network fetch request"
    strict, strict_reason = _strict_runtime_controls(argv[: argv.index(git_image)], command="run-git")
    if not strict:
        return False, strict_reason
    git_index = argv.index("/usr/bin/git")
    git_args = argv[git_index + 1 :]
    if "--git-dir" not in git_args:
        return False, "network fetch lacks git-dir"
    git_dir = git_args[git_args.index("--git-dir") + 1]
    if not git_dir.endswith("/acquisition/repository.git"):
        return False, "network fetch target is not the candidate acquisition repository"
    return True, ""

def classify_broker_argv(
    argv: object,
    *,
    git_image: str,
    sandbox_image_id: str,
    canonical_url: str,
    created: set[str],
) -> tuple[bool, str, str]:
    if isinstance(argv, list) and argv and argv[0] in {"run", "create"}:
        try:
            if argv[0] == "run" and git_image in argv:
                before = argv[: argv.index(git_image)]
                strict, reason = _strict_runtime_controls(before, command="run-git")
                if not strict:
                    return False, "run-git", reason
            elif argv[0] == "create" and sandbox_image_id in argv:
                before = argv[: argv.index(sandbox_image_id)]
                strict, reason = _strict_runtime_controls(before, command="create-sandbox")
                if not strict:
                    return False, "create-sandbox", reason
        except (ValueError, IndexError):
            return False, "invalid", "container command cannot be parsed"

    allowed, command_class, reason = _baseline_classify_broker_argv(
        argv,
        git_image=git_image,
        sandbox_image_id=sandbox_image_id,
        canonical_url=canonical_url,
        created=created,
    )
    if allowed and command_class == "run-git-network":
        return (
            False,
            "run-git-network",
            "candidate-writable Git state cannot be the authority for network acquisition",
        )
    return allowed, command_class, reason

def plan_broker_request(
    argv: object,
    *,
    git_image: str,
    sandbox_image_id: str,
    canonical_url: str,
    created: set[str],
) -> tuple[bool, str, str]:
    legacy, reason = _legacy_network_fetch_request(
        argv, git_image=git_image, canonical_url=canonical_url
    )
    if legacy:
        return True, "broker-owned-acquisition", ""
    return classify_broker_argv(
        argv,
        git_image=git_image,
        sandbox_image_id=sandbox_image_id,
        canonical_url=canonical_url,
        created=created,
    )

def _container_security_summary(inspect: dict[str, Any]) -> dict[str, Any]:
    config = inspect.get("Config") if isinstance(inspect.get("Config"), dict) else {}
    host = inspect.get("HostConfig") if isinstance(inspect.get("HostConfig"), dict) else {}
    return {
        "id": inspect.get("Id"),
        "user": config.get("User"),
        "readonly_rootfs": host.get("ReadonlyRootfs"),
        "tmpfs": host.get("Tmpfs") or {},
        "runtime": host.get("Runtime") or "",
        "group_add": host.get("GroupAdd") or [],
        "network_mode": host.get("NetworkMode"),
        "mounts": [
            {
                "type": item.get("Type"),
                "source": item.get("Source"),
                "destination": item.get("Destination"),
                "rw": item.get("RW"),
            }
            for item in (inspect.get("Mounts") or [])
            if isinstance(item, dict)
        ],
    }

def _run_created_container(
    host: str, create_argv: list[str], *, timeout: int = 240
) -> tuple[int, str, str, dict[str, Any]]:
    created = subprocess.run(
        ["docker", "-H", host, *create_argv],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if created.returncode != 0:
        return created.returncode, created.stdout, created.stderr, {}
    container_id = created.stdout.strip()
    inspected = subprocess.run(
        ["docker", "-H", host, "inspect", container_id],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, check=False,
    )
    if inspected.returncode != 0:
        subprocess.run(["docker", "-H", host, "rm", "-f", container_id], check=False)
        return 125, "", inspected.stderr, {}
    values = json.loads(inspected.stdout)
    if len(values) != 1:
        subprocess.run(["docker", "-H", host, "rm", "-f", container_id], check=False)
        return 125, "", "ambiguous container inspect", {}
    summary = _container_security_summary(values[0])
    for mount in summary["mounts"]:
        source = str(mount.get("source") or "")
        if mount.get("type") == "bind" and not source.startswith("/runs/"):
            subprocess.run(["docker", "-H", host, "rm", "-f", container_id], check=False)
            return 125, "", f"trusted mount resolution escaped /runs: {source}", summary
    started = subprocess.run(
        ["docker", "-H", host, "start", "-a", container_id],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    subprocess.run(
        ["docker", "-H", host, "rm", "-f", container_id],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    return started.returncode, started.stdout, started.stderr, summary

def _execute_broker_owned_acquisition(
    *, host: str, argv: list[str], git_image: str, request_id: str
) -> tuple[int, str, str, dict[str, Any]]:
    image_index = argv.index(git_image)
    before = argv[:image_index]
    mounts = _option(before, "--mount")
    if len(mounts) != 1:
        return 125, "", "broker-owned acquisition requires one candidate output mount", {}
    fields = _parse_mount(mounts[0])
    output_source = fields.get("src") or fields.get("source")
    if not isinstance(output_source, str) or not output_source.startswith("/runs/"):
        return 125, "", "candidate output root is outside /runs", {}
    git_index = argv.index("/usr/bin/git")
    git_args = argv[git_index + 1 :]
    refspec = git_args[-1]
    commit = refspec[1:41]
    volume = "p1-acq-" + hashlib.sha256(request_id.encode()).hexdigest()[:24]

    volume_create = subprocess.run(
        ["docker", "-H", host, "volume", "create", volume],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30, check=False,
    )
    if volume_create.returncode != 0:
        return volume_create.returncode, volume_create.stdout, volume_create.stderr, {}

    common = [
        "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "128", "--memory", "512m", "--cpus", "1",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864",
    ]
    init_script = (
        "set -eu; mkdir -p /trusted/repository.git; "
        "/usr/bin/git init --bare /trusted/repository.git >/dev/null; "
        "/usr/bin/git --git-dir /trusted/repository.git config --local core.hooksPath /dev/null; "
        "/usr/bin/git --git-dir /trusted/repository.git config --local credential.helper ''; "
        "/usr/bin/git --git-dir /trusted/repository.git config --local http.followRedirects false; "
        "chown -R 1000:1000 /trusted"
    )
    init_create = [
        "create", "--network", "none", *common, "--user", "0:0",
        "--mount", f"type=volume,src={volume},dst=/trusted,rw",
        "--entrypoint", "/bin/busybox", git_image, "sh", "-eu", "-c", init_script,
    ]
    rc, out, err, _ = _run_created_container(host, init_create)
    if rc != 0:
        subprocess.run(["docker", "-H", host, "volume", "rm", "-f", volume], check=False)
        return rc, out, err, {}

    fetch_create = [
        "create", "--platform", "linux/amd64", "--network", "bridge",
        *common, "--user", "1000:1000", "--workdir", "/trusted",
        "--mount", f"type=volume,src={volume},dst=/trusted,rw",
        "--entrypoint", "/bin/busybox", git_image,
        "env", "-i", *GIT_ENVIRONMENT, "/usr/bin/git", *FETCH_CONFIG,
        "--git-dir", "/trusted/repository.git", "fetch",
        "--no-tags", "--no-recurse-submodules", "--depth=1", CANONICAL_URL,
        f"+{commit}:refs/executor/input",
    ]
    rc, out, err, inspection = _run_created_container(host, fetch_create)
    if rc != 0:
        subprocess.run(["docker", "-H", host, "volume", "rm", "-f", volume], check=False)
        return rc, out, err, inspection

    copy_script = (
        "set -eu; rm -rf /output/acquisition/repository.git; "
        "mkdir -p /output/acquisition; "
        "cp -a /trusted/repository.git /output/acquisition/repository.git"
    )
    copy_create = [
        "create", "--network", "none", *common, "--user", "1000:1000",
        "--mount", f"type=volume,src={volume},dst=/trusted,readonly",
        "--mount", f"type=bind,src={output_source},dst=/output,rw",
        "--entrypoint", "/bin/busybox", git_image, "sh", "-eu", "-c", copy_script,
    ]
    copy_rc, copy_out, copy_err, _ = _run_created_container(host, copy_create)
    subprocess.run(
        ["docker", "-H", host, "volume", "rm", "-f", volume],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if copy_rc != 0:
        return copy_rc, copy_out, copy_err, inspection
    return rc, out, err, inspection

class _BrokerState:
    def __init__(self, *, max_events: int, events_path: Path) -> None:
        self.max_events = max_events
        self.events_path = events_path
        self.lock = threading.Lock()
        self.sequence = 0
        self.overflow = False
        self.created: set[str] = set()
        events_path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = events_path.open("w", encoding="utf-8")

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.sequence += 1
            if self.sequence > self.max_events:
                self.overflow = True
                raise RuntimeError("broker event limit exceeded")
            value = {"sequence": self.sequence, **event}
            self.stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
            self.stream.flush()
            os.fsync(self.stream.fileno())
            return value

    def close(self) -> None:
        self.stream.close()

def run_docker_command_broker(
    *,
    host: str,
    socket_path: Path,
    approved_path: Path,
    events_path: Path,
    ready_path: Path,
    status_path: Path,
    git_image: str,
    sandbox_image: str,
    canonical_url: str,
    max_events: int,
) -> int:
    approved = json.loads(approved_path.read_text(encoding="utf-8"))["images"]
    sandbox_image_id = approved[sandbox_image]["id"]
    state = _BrokerState(max_events=max_events, events_path=events_path)
    broker_error: str | None = None
    server: socketserver.ThreadingUnixStreamServer | None = None

    class Handler(socketserver.StreamRequestHandler):
        def handle(self) -> None:
            try:
                header = self.rfile.read(8)
                if len(header) != 8:
                    raise ValueError("short request header")
                size = int.from_bytes(header, "big")
                if size <= 0 or size > 131072:
                    raise ValueError("request size outside limit")
                payload = self.rfile.read(size)
                if len(payload) != size:
                    raise ValueError("short request body")
                request = json.loads(payload)
                argv = request.get("argv")
                allowed, command_class, reason = plan_broker_request(
                    argv,
                    git_image=git_image,
                    sandbox_image_id=sandbox_image_id,
                    canonical_url=canonical_url,
                    created=state.created,
                )
                request_id = f"request-{time.time_ns()}"
                request_event = state.append(
                    {
                        "phase": "request",
                        "request_id": request_id,
                        "argv": argv,
                        "argv_sha256": _sha256_bytes(_canonical_bytes(argv)),
                        "decision": "ALLOW" if allowed else "DENY",
                        "command_class": command_class,
                        "reason": reason,
                        "case_id": _case_id_from_argv(argv) if isinstance(argv, list) else None,
                    }
                )
                started = time.monotonic()
                inspection: dict[str, Any] = {}
                if allowed and command_class == "broker-owned-acquisition":
                    returncode, stdout, stderr, inspection = _execute_broker_owned_acquisition(
                        host=host, argv=argv, git_image=git_image, request_id=request_id
                    )
                elif allowed:
                    completed = subprocess.run(
                        ["docker", "-H", host, *argv],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=240,
                        check=False,
                    )
                    stdout, stderr, returncode = (
                        completed.stdout, completed.stderr, completed.returncode
                    )
                    if argv[0] == "create" and returncode == 0:
                        names = _option(argv, "--name")
                        if len(names) == 1:
                            with state.lock:
                                state.created.add(names[0])
                            inspected = subprocess.run(
                                ["docker", "-H", host, "inspect", names[0]],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=30, check=False,
                            )
                            if inspected.returncode == 0:
                                values = json.loads(inspected.stdout)
                                if len(values) == 1:
                                    inspection = _container_security_summary(values[0])
                    if argv[0] == "rm" and returncode == 0:
                        with state.lock:
                            state.created.discard(argv[-1])
                else:
                    stdout, stderr, returncode = "", reason, 126
                response = {
                    "returncode": returncode,
                    "stdout": stdout[:16777216],
                    "stderr": stderr[:16777216],
                }
                state.append(
                    {
                        "phase": "response",
                        "request_id": request_id,
                        "request_argv_sha256": request_event["argv_sha256"],
                        "returncode": returncode,
                        "stdout_sha256": _sha256_text(response["stdout"]),
                        "stderr_sha256": _sha256_text(response["stderr"]),
                        "duration_seconds": time.monotonic() - started,
                        "inspection": inspection or None,
                        "inspection_sha256": (
                            _sha256_bytes(_canonical_bytes(inspection)) if inspection else None
                        ),
                    }
                )
                encoded = json.dumps(response, sort_keys=True).encode()
                self.wfile.write(len(encoded).to_bytes(8, "big") + encoded)
            except Exception as exc:
                encoded = json.dumps(
                    {
                        "returncode": 125,
                        "stdout": "",
                        "stderr": f"BROKER_ERROR: {type(exc).__name__}: {exc}",
                    },
                    sort_keys=True,
                ).encode()
                try:
                    self.wfile.write(len(encoded).to_bytes(8, "big") + encoded)
                except Exception:
                    pass

    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True
        allow_reuse_address = True

    try:
        socket_path.unlink(missing_ok=True)
        server = Server(str(socket_path), Handler)
        os.chmod(socket_path, 0o666)
        _write_json(
            ready_path,
            {"ready_before_candidate": True, "broker_authority": BROKER_AUTHORITY},
        )

        def stop(_signum, _frame) -> None:
            assert server is not None
            threading.Thread(target=server.shutdown, daemon=True).start()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        server.serve_forever(poll_interval=0.1)
    except Exception as exc:
        broker_error = f"{type(exc).__name__}: {exc}"
    finally:
        if server is not None:
            server.server_close()
        state.close()
        socket_path.unlink(missing_ok=True)
        _write_json(
            status_path,
            {
                "broker_authority": BROKER_AUTHORITY,
                "complete": broker_error is None and not state.overflow,
                "overflow": state.overflow,
                "broker_error": broker_error,
                "event_count": state.sequence,
            },
        )
    return 0 if broker_error is None and not state.overflow else 1

def _verify_inspection(
    inspection: object, *, expected_user: str, errors: list[str], label: str
) -> None:
    if not isinstance(inspection, dict):
        errors.append(f"{label} trusted inspection is missing")
        return
    if inspection.get("user") != expected_user:
        errors.append(f"{label} user identity mismatch")
    if inspection.get("readonly_rootfs") is not True:
        errors.append(f"{label} root filesystem is writable")
    if inspection.get("group_add") not in (None, []):
        errors.append(f"{label} has unapproved supplementary groups")
    tmpfs = inspection.get("tmpfs")
    if not isinstance(tmpfs, dict) or "/tmp" not in tmpfs:
        errors.append(f"{label} tmpfs evidence is incomplete")
    if "/executor-run" in tmpfs:
        errors.append(f"{label} shadows the authorized run mount")
    runtime = inspection.get("runtime")
    if runtime not in KNOWN_RUNTIMES:
        errors.append(f"{label} runtime is outside the trusted defaults")

def verify_broker_evidence(execution_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        ledger = json.loads(
            (execution_dir / "docker-command-ledger.json").read_text(encoding="utf-8")
        )
    except Exception as exc:
        ledger = {}
        errors.append(f"trusted Docker command broker ledger missing or invalid: {exc}")
    for field, expected, message in (
        ("schema_version", 1, "trusted Docker command broker ledger schema mismatch"),
        ("broker_authority", BROKER_AUTHORITY, "trusted Docker command broker authority mismatch"),
        ("ready_before_candidate", True, "trusted Docker command broker was not ready before candidate"),
        ("complete", True, "trusted Docker command broker ledger is incomplete"),
        ("overflow", False, "trusted Docker command broker ledger overflowed"),
        ("candidate_endpoint", BROKER_ENDPOINT, "candidate endpoint is not the trusted broker"),
        ("direct_daemon_endpoint_exposed", False, "raw Docker endpoint was exposed"),
    ):
        if ledger.get(field) != expected:
            errors.append(message)
    if ledger.get("broker_error") not in (None, ""):
        errors.append("trusted Docker command broker reported an error")

    events = ledger.get("events")
    if not isinstance(events, list) or not events:
        errors.append("trusted Docker command broker ledger has no events")
        events = []
    requests: dict[str, dict[str, Any]] = {}
    responses: dict[str, dict[str, Any]] = {}
    created: set[str] = set()
    acquisition_cases: set[str] = set()
    sandbox_cases: set[str] = set()

    for expected_sequence, event in enumerate(events, 1):
        if not isinstance(event, dict):
            errors.append("broker ledger contains a non-object event")
            continue
        if event.get("sequence") != expected_sequence:
            errors.append("broker ledger sequence is not contiguous")
        request_id = event.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            errors.append("broker event lacks request identity")
            continue
        if event.get("phase") == "request":
            if request_id in requests:
                errors.append("broker request identity is duplicated")
            requests[request_id] = event
            argv = event.get("argv")
            if event.get("argv_sha256") != _sha256_bytes(_canonical_bytes(argv)):
                errors.append("broker request argv hash mismatch")
            command_class = event.get("command_class")
            if event.get("decision") != "ALLOW":
                errors.append("broker recorded a denied or unknown request")
            if command_class == "broker-owned-acquisition":
                valid, reason = _legacy_network_fetch_request(
                    argv, git_image=GIT_IMAGE_REF, canonical_url=CANONICAL_URL
                )
                if not valid:
                    errors.append(f"broker-owned acquisition request is invalid: {reason}")
            else:
                allowed, expected_class, reason = classify_broker_argv(
                    argv,
                    git_image=GIT_IMAGE_REF,
                    sandbox_image_id=_sandbox_image_id(execution_dir, errors),
                    canonical_url=CANONICAL_URL,
                    created=created,
                )
                if not allowed:
                    errors.append(f"broker ledger contains command outside exact grammar: {reason}")
                if command_class != expected_class:
                    errors.append("broker command class mismatch")
        elif event.get("phase") == "response":
            if request_id in responses:
                errors.append("broker response identity is duplicated")
            responses[request_id] = event
            request = requests.get(request_id)
            if request is not None:
                if event.get("request_argv_sha256") != request.get("argv_sha256"):
                    errors.append("broker response is not bound to its request")
                command_class = request.get("command_class")
                returncode = event.get("returncode")
                if not isinstance(returncode, int):
                    errors.append("broker response returncode is missing or invalid")
                elif command_class in {"create-sandbox", "broker-owned-acquisition"} and returncode != 0:
                    errors.append(
                        f"required CASE operation {command_class} returned nonzero returncode {returncode}"
                    )
                if returncode == 0:
                    case_id = request.get("case_id") or _case_id_from_argv(request.get("argv") or [])
                    if command_class == "create-sandbox":
                        _verify_inspection(
                            event.get("inspection"),
                            expected_user="65534:65534",
                            errors=errors,
                            label="sandbox",
                        )
                        if case_id in CASE_IDS:
                            sandbox_cases.add(case_id)
                        names = _option(request.get("argv") or [], "--name")
                        if len(names) == 1:
                            created.add(names[0])
                    elif command_class == "broker-owned-acquisition":
                        _verify_inspection(
                            event.get("inspection"),
                            expected_user="1000:1000",
                            errors=errors,
                            label="network acquisition",
                        )
                        if case_id in CASE_IDS:
                            acquisition_cases.add(case_id)
                    elif command_class == "remove-container":
                        argv = request.get("argv") or []
                        if argv:
                            created.discard(argv[-1])
        else:
            errors.append("broker event phase is invalid")

    if set(requests) != set(responses):
        errors.append("broker request/response sequence is incomplete")
    missing_acquisition = sorted(CASE_IDS - acquisition_cases)
    missing_sandbox = sorted(CASE_IDS - sandbox_cases)
    if missing_acquisition or missing_sandbox:
        errors.append(
            "execution transcript missing CASE-001–003 acquisition or sandbox operations: "
            f"acquisition={missing_acquisition}, sandbox={missing_sandbox}"
        )

    return {
        "verified": not errors,
        "events": len(events),
        "requests": len(requests),
        "responses": len(responses),
        "acquisition_cases": sorted(acquisition_cases),
        "sandbox_cases": sorted(sandbox_cases),
        "errors": sorted(set(errors)),
    }

def _sandbox_image_id(execution_dir: Path, errors: list[str]) -> str:
    try:
        approved = json.loads(
            (execution_dir / "approved-nested-images.json").read_text(encoding="utf-8")
        )
        return approved["images"][SANDBOX_IMAGE_REF]["id"]
    except Exception as exc:
        errors.append(f"trusted approved image evidence missing or invalid: {exc}")
        return "<missing-sandbox-image>"

def apply_broker_gate(
    *, execution_dir: Path, gate_path: Path, output_path: Path
) -> dict[str, Any]:
    summary = verify_broker_evidence(execution_dir)
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except Exception as exc:
        gate = {
            "schema_version": 2,
            "authoritative_result": "FAIL",
            "errors": [f"authoritative gate missing before broker verification: {exc}"],
            "warnings": [],
        }
    errors = list(gate.get("errors") or [])
    errors.extend(summary["errors"])
    gate["errors"] = sorted(set(str(item) for item in errors))
    gate["docker_command_broker_summary"] = {
        key: value for key, value in summary.items() if key != "errors"
    }
    if gate["errors"]:
        gate["authoritative_result"] = "FAIL"
    _write_json(gate_path, gate)
    _write_json(output_path, summary)
    return gate

class AdversarialBrokerRegressionTests(unittest.TestCase):
    def _network_git_argv(self) -> list[str]:
        commit = "1" * 40
        return [
            "run", "--rm", "--platform", "linux/amd64", "--network", "bridge",
            "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "128", "--memory", "512m", "--cpus", "1",
            "--user", "1000:1000",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--workdir", "/executor-run",
            "--mount", "type=bind,src=/runs/case-001/pilot-run,dst=/executor-run,rw",
            "--entrypoint", "/bin/busybox", "git-image",
            "env", "-i", *GIT_ENVIRONMENT, "/usr/bin/git", *FETCH_CONFIG,
            "--git-dir", "/executor-run/acquisition/repository.git", "fetch",
            "--no-tags", "--no-recurse-submodules", "--depth=1", CANONICAL_URL,
            f"+{commit}:refs/executor/input",
        ]

    def test_classifier_rejects_root_writable_and_extra_runtime_authority(self):
        attacks = {
            "root-user": ["--user", "0:0"],
            "writable-root": ["--read-only=false"],
            "shadow-executor-run": ["--tmpfs", "/executor-run:rw"],
            "unapproved-runtime": ["--runtime", "runc"],
        }
        for label, extra in attacks.items():
            with self.subTest(label=label):
                argv = self._network_git_argv()
                image_index = argv.index("git-image")
                argv[image_index:image_index] = extra
                allowed, _, reason = classify_broker_argv(
                    argv,
                    git_image="git-image",
                    sandbox_image_id="sandbox-image-id",
                    canonical_url=CANONICAL_URL,
                    created=set(),
                )
                self.assertFalse(
                    allowed, f"authority downgrade was accepted: {label}: {reason}"
                )

    def test_network_fetch_cannot_trust_candidate_writable_git_configuration(self):
        argv = self._network_git_argv()
        allowed, _, _ = classify_broker_argv(
            argv,
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertFalse(
            allowed,
            "candidate-writable repository.git/config can rewrite the effective HTTPS endpoint",
        )
        planned, command_class, reason = plan_broker_request(
            argv,
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertTrue(planned, reason)
        self.assertEqual(command_class, "broker-owned-acquisition")

    def test_legal_sandbox_remains_allowed(self):
        argv = [
            "create",
            "--name", "cos-executor-abcdef123456",
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", "16",
            "--memory", "64m",
            "--cpus", "1.0",
            "--user", "65534:65534",
            "--env", "HOME=/nonexistent",
            "--workdir", "/source",
            "--mount",
            "type=bind,src=/candidate/tests/fixtures/sandbox,dst=/source,readonly",
            "--tmpfs", "/workspace:rw,nosuid,nodev,size=8m,mode=1777",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "sandbox-image-id",
            "python", "/source/sandbox_fixture.py", "read_source",
        ]
        allowed, command_class, reason = classify_broker_argv(
            argv,
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertTrue(allowed, reason)
        self.assertEqual(command_class, "create-sandbox")

    def test_version_only_broker_ledger_cannot_preserve_authoritative_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            execution = Path(temporary)
            argv = ["version", "--format", "{{.Server.Version}}"]
            argv_hash = _sha256_bytes(_canonical_bytes(argv))
            _write_json(
                execution / "docker-command-ledger.json",
                {
                    "schema_version": 1,
                    "broker_authority": BROKER_AUTHORITY,
                    "ready_before_candidate": True,
                    "complete": True,
                    "overflow": False,
                    "broker_error": None,
                    "candidate_endpoint": BROKER_ENDPOINT,
                    "direct_daemon_endpoint_exposed": False,
                    "events": [
                        {
                            "sequence": 1,
                            "phase": "request",
                            "request_id": "request-000001",
                            "argv": argv,
                            "argv_sha256": argv_hash,
                            "decision": "ALLOW",
                            "command_class": "version",
                        },
                        {
                            "sequence": 2,
                            "phase": "response",
                            "request_id": "request-000001",
                            "request_argv_sha256": argv_hash,
                            "returncode": 0,
                            "stdout_sha256": _sha256_text("27.5.1\n"),
                            "stderr_sha256": _sha256_text(""),
                        },
                    ],
                },
            )
            _write_json(
                execution / "approved-nested-images.json",
                {"images": {SANDBOX_IMAGE_REF: {"id": "sha256:" + "2" * 64}}},
            )
            gate_path = execution / "authoritative-final-gate.json"
            _write_json(
                gate_path,
                {
                    "schema_version": 2,
                    "authoritative_result": "PASS",
                    "errors": [],
                    "warnings": [],
                },
            )
            gate = apply_broker_gate(
                execution_dir=execution,
                gate_path=gate_path,
                output_path=execution / "docker-command-broker-verification.json",
            )
            self.assertEqual(gate["authoritative_result"], "FAIL")
            self.assertTrue(
                any("execution transcript" in error.lower() for error in gate["errors"]),
                gate["errors"],
            )


class AdversarialReplayRegressionTests(unittest.TestCase):
    def _sandbox_argv(self, case_id: str = "001") -> list[str]:
        image = "sha256:" + "2" * 64
        return [
            "create", "--name", f"cos-executor-{case_id}",
            "--network", "none", "--read-only",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "16", "--memory", "64m", "--cpus", "1.0",
            "--user", "65534:65534", "--env", "HOME=/nonexistent",
            "--workdir", "/source", "--mount",
            f"type=bind,src=/candidate/case-{case_id}/tests/fixtures/sandbox,dst=/source,readonly",
            "--tmpfs", "/workspace:rw,nosuid,nodev,size=8m,mode=1777",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            image, "python", "/source/sandbox_fixture.py", "read_source",
        ]

    def _network_argv(self, case_id: str) -> list[str]:
        commit = {"001": "1", "002": "2", "003": "3"}[case_id] * 40
        argv = AdversarialBrokerRegressionTests()._network_git_argv()
        argv = [
            item.replace("/runs/case-001/", f"/runs/case-{case_id}/")
            for item in argv
        ]
        argv[argv.index("git-image")] = GIT_IMAGE_REF
        argv[-1] = f"+{commit}:refs/executor/input"
        return argv

    def test_rejects_unapproved_supplementary_root_group(self):
        argv = self._sandbox_argv()
        image_index = argv.index("sha256:" + "2" * 64)
        argv[image_index:image_index] = ["--group-add", "0"]
        allowed, _, reason = classify_broker_argv(
            argv,
            git_image="git-image",
            sandbox_image_id="sha256:" + "2" * 64,
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertFalse(allowed, f"supplementary root group accepted: {reason}")

    def test_failed_required_case_operations_force_authoritative_fail(self):
        events: list[dict[str, Any]] = []
        sequence = 0

        def pair(request_id: str, argv: list[str], command_class: str, case_id: str) -> None:
            nonlocal sequence
            argv_hash = _sha256_bytes(_canonical_bytes(argv))
            sequence += 1
            events.append({
                "sequence": sequence,
                "phase": "request",
                "request_id": request_id,
                "argv": argv,
                "argv_sha256": argv_hash,
                "decision": "ALLOW",
                "command_class": command_class,
                "reason": "",
                "case_id": case_id,
            })
            sequence += 1
            events.append({
                "sequence": sequence,
                "phase": "response",
                "request_id": request_id,
                "request_argv_sha256": argv_hash,
                "returncode": 125,
                "stdout_sha256": _sha256_text(""),
                "stderr_sha256": _sha256_text("failed"),
                "duration_seconds": 0.01,
                "inspection": None,
                "inspection_sha256": None,
            })

        for case_id in ("001", "002", "003"):
            pair(
                f"acquisition-{case_id}",
                self._network_argv(case_id),
                "broker-owned-acquisition",
                case_id,
            )
            pair(
                f"sandbox-{case_id}",
                self._sandbox_argv(case_id),
                "create-sandbox",
                case_id,
            )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write_json(root / "docker-command-ledger.json", {
                "schema_version": 1,
                "broker_authority": BROKER_AUTHORITY,
                "ready_before_candidate": True,
                "complete": True,
                "overflow": False,
                "broker_error": None,
                "candidate_endpoint": BROKER_ENDPOINT,
                "direct_daemon_endpoint_exposed": False,
                "events": events,
            })
            _write_json(root / "approved-nested-images.json", {
                "images": {SANDBOX_IMAGE_REF: {"id": "sha256:" + "2" * 64}},
            })
            gate_path = root / "authoritative-final-gate.json"
            _write_json(gate_path, {
                "schema_version": 2,
                "authoritative_result": "PASS",
                "errors": [],
                "warnings": [],
            })
            gate = apply_broker_gate(
                execution_dir=root,
                gate_path=gate_path,
                output_path=root / "broker-verification.json",
            )
            self.assertEqual(gate["authoritative_result"], "FAIL", gate)
            self.assertTrue(
                any("returncode" in error.lower() for error in gate["errors"]),
                gate["errors"],
            )

    def test_verifier_accepts_only_exact_broker_owned_volume_contract(self):
        spec = importlib.util.spec_from_file_location(
            "p1_authoritative_verifier",
            ROOT / "tools/p1_verifier/verify_candidate.py",
        )
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        pattern = r"^p1-acq-[0-9a-f]{24}$"
        valid = {
            "Type": "volume",
            "Name": "p1-acq-" + "a" * 24,
            "Source": "/rootless/docker/volumes/internal/_data",
            "Destination": "/trusted",
            "RW": True,
        }
        self.assertTrue(module._trusted_nested_mount_allowed(
            valid,
            allowed_bind_sources=["/candidate", "/runs"],
            trusted_volume_pattern=pattern,
            image_ref=GIT_IMAGE_REF,
            acquisition_image=GIT_IMAGE_REF,
        ))
        wrong_name = dict(valid, Name="candidate-volume")
        self.assertFalse(module._trusted_nested_mount_allowed(
            wrong_name,
            allowed_bind_sources=["/candidate", "/runs"],
            trusted_volume_pattern=pattern,
            image_ref=GIT_IMAGE_REF,
            acquisition_image=GIT_IMAGE_REF,
        ))
        wrong_image = dict(valid)
        self.assertFalse(module._trusted_nested_mount_allowed(
            wrong_image,
            allowed_bind_sources=["/candidate", "/runs"],
            trusted_volume_pattern=pattern,
            image_ref=SANDBOX_IMAGE_REF,
            acquisition_image=GIT_IMAGE_REF,
        ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--verify-broker", action="store_true")
    mode.add_argument("--serve-broker", action="store_true")
    parser.add_argument("--execution-dir", type=Path)
    parser.add_argument("--gate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--host")
    parser.add_argument("--socket", type=Path)
    parser.add_argument("--approved", type=Path)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--ready", type=Path)
    parser.add_argument("--status", type=Path)
    parser.add_argument("--git-image")
    parser.add_argument("--sandbox-image")
    parser.add_argument("--canonical-url")
    parser.add_argument("--max-events", type=int, default=8192)
    args = parser.parse_args(argv)
    if args.serve_broker:
        required = {
            "host": args.host,
            "socket": args.socket,
            "approved": args.approved,
            "events": args.events,
            "ready": args.ready,
            "status": args.status,
            "git_image": args.git_image,
            "sandbox_image": args.sandbox_image,
            "canonical_url": args.canonical_url,
        }
        missing = sorted(key for key, value in required.items() if value is None)
        if missing:
            parser.error(f"missing broker arguments: {', '.join(missing)}")
        return run_docker_command_broker(
            host=args.host,
            socket_path=args.socket.resolve(),
            approved_path=args.approved.resolve(),
            events_path=args.events.resolve(),
            ready_path=args.ready.resolve(),
            status_path=args.status.resolve(),
            git_image=args.git_image,
            sandbox_image=args.sandbox_image,
            canonical_url=args.canonical_url,
            max_events=args.max_events,
        )
    if args.execution_dir is None or args.gate is None or args.output is None:
        parser.error("--execution-dir, --gate and --output are required")
    gate = apply_broker_gate(
        execution_dir=args.execution_dir.resolve(),
        gate_path=args.gate.resolve(),
        output_path=args.output.resolve(),
    )
    print(json.dumps(gate, sort_keys=True, indent=2))
    return 0 if gate.get("authoritative_result") == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
