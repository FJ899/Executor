from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import os
import re
import signal
import socketserver
import threading
import time
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/manual-exact-ref-verify.yml"
ACCEPTANCE = ROOT / "tools/p1_verifier/acceptance_manifest.json"
BASELINE_SHA = "f1188f9edd20f67a96494e33a109381f1a5bf331"
BASELINE_TEST_PATH = "tests/test_p1_verifier.py"
CANONICAL_URL = "https://github.com/litrgratis-pixel/executor-pilot-target.git"
GIT_IMAGE_REF = "alpine/git@sha256:0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd"
SANDBOX_IMAGE_REF = "python@sha256:b18992999dbe963a45a8a4da40ac2b1975be1a776d939d098c647482bcad5cba"
BROKER_AUTHORITY = "TRUSTED_HOST_HARNESS"
BROKER_ENDPOINT = "UNIX_COMMAND_BROKER_ONLY"
BROKER_CLASSES = {
    "version",
    "image-inspect",
    "run-git-network",
    "run-git-offline",
    "create-sandbox",
    "ps-container",
    "inspect-container",
    "start-container",
    "kill-container",
    "wait-container",
    "remove-container",
}


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


def verify(**kwargs):
    from tools.p1_verifier.verify_candidate import verify as implementation

    return implementation(**kwargs)


def _option(argv: list[str], name: str) -> list[str]:
    values: list[str] = []
    for index, item in enumerate(argv):
        if item == name and index + 1 < len(argv):
            values.append(argv[index + 1])
        elif item.startswith(name + "="):
            values.append(item.split("=", 1)[1])
    return values


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
    return any(
        item in forbidden_exact or item.startswith(forbidden_prefixes)
        for item in argv
    )


def _hardened(argv: list[str]) -> bool:
    return (
        "--read-only" in argv
        and ("--cap-drop=ALL" in argv or _option(argv, "--cap-drop") == ["ALL"])
        and (
            "--security-opt=no-new-privileges" in argv
            or _option(argv, "--security-opt") == ["no-new-privileges"]
        )
        and not _has_forbidden_runtime_option(argv)
        and _option(argv, "--network") not in (["host"], ["container"])
    )


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
        item.startswith("alias.")
        or "!" in item
        or item in {"--config-env", "--exec-path", "--upload-pack"}
        for item in git_args
    ):
        return False
    if (
        len(git_args) == 3
        and git_args[:2] == ["init", "--bare"]
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
            or item.startswith("alias.")
            or "!" in item
            or "://" in item
            for item in rest[1:]
        ):
            return False
        if rest[0] == "switch":
            return (
                len(rest) == 3
                and rest[1] == "-c"
                and BRANCH_RE.fullmatch(rest[2]) is not None
            )
        return True
    if rest[:2] == ["worktree", "add"]:
        return (
            len(rest) == 5
            and rest[2] == "--detach"
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


def classify_broker_argv(
    argv: object,
    *,
    git_image: str,
    sandbox_image_id: str,
    canonical_url: str,
    created: set[str],
) -> tuple[bool, str, str]:
    if (
        not isinstance(argv, list)
        or not argv
        or not all(
            isinstance(item, str)
            and item
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
        len(argv) == 5
        and argv[:3] == ["image", "inspect", "--format"]
        and argv[4] == git_image
    ):
        return True, "image-inspect", ""
    if argv[0] == "run":
        if argv.count(git_image) != 1 or not _hardened(argv):
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
        if len(mounts) != 1 or not _safe_mount(
            mounts[0], "/executor-run", readonly=False
        ):
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
        if argv.count(sandbox_image_id) != 1 or not _hardened(argv):
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
        if _option(before, "--user") != ["65534:65534"] or _option(
            before, "--workdir"
        ) != ["/source"]:
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
            len(command) == 3
            and command[:2] == ["python", "/source/sandbox_fixture.py"]
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
            "start": "start-container",
            "kill": "kill-container",
            "wait": "wait-container",
            "rm": "remove-container",
        }
        return True, classes[argv[0]], ""
    return False, "unknown", f"unknown Docker command: {argv[0]}"


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
                allowed, command_class, reason = classify_broker_argv(
                    argv,
                    git_image=git_image,
                    sandbox_image_id=sandbox_image_id,
                    canonical_url=canonical_url,
                    created=state.created,
                )
                request_event = state.append(
                    {
                        "phase": "request",
                        "request_id": f"request-{time.time_ns()}",
                        "argv": argv,
                        "argv_sha256": _sha256_bytes(_canonical_bytes(argv)),
                        "decision": "ALLOW" if allowed else "DENY",
                        "command_class": command_class,
                        "reason": reason,
                    }
                )
                request_id = request_event["request_id"]
                started = time.monotonic()
                if allowed:
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
                    stdout = completed.stdout
                    stderr = completed.stderr
                    returncode = completed.returncode
                    if argv[0] == "create" and returncode == 0:
                        with state.lock:
                            state.created.add(_option(argv, "--name")[0])
                    if argv[0] == "rm" and returncode == 0:
                        with state.lock:
                            state.created.discard(argv[-1])
                else:
                    stdout = ""
                    stderr = reason
                    returncode = 126
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
                    }
                )
                encoded = json.dumps(response, sort_keys=True).encode()
                self.wfile.write(len(encoded).to_bytes(8, "big") + encoded)
            except Exception as exc:
                try:
                    encoded = json.dumps(
                        {
                            "returncode": 125,
                            "stdout": "",
                            "stderr": f"BROKER_ERROR: {type(exc).__name__}: {exc}",
                        },
                        sort_keys=True,
                    ).encode()
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
            {
                "ready_before_candidate": True,
                "broker_authority": BROKER_AUTHORITY,
            },
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


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode())


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(value))


def _contains_raw_daemon_claim(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("daemon_network_request") is True:
            return True
        if value.get("raw_docker_api") is True:
            return True
        return any(_contains_raw_daemon_claim(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_raw_daemon_claim(item) for item in value)
    return False


def verify_broker_evidence(execution_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    ledger_path = execution_dir / "docker-command-ledger.json"
    network_path = execution_dir / "network-observation.json"
    observation_path = execution_dir / "observation-manifest.json"
    approved_path = execution_dir / "approved-nested-images.json"

    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as exc:
        ledger = {}
        errors.append(f"trusted Docker command broker ledger missing or invalid: {exc}")
    try:
        network = json.loads(network_path.read_text(encoding="utf-8"))
    except Exception as exc:
        network = {}
        errors.append(f"trusted broker network observation missing or invalid: {exc}")
    try:
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
    except Exception as exc:
        observation = {}
        errors.append(f"execution observation missing or invalid for broker verification: {exc}")
    try:
        approved = json.loads(approved_path.read_text(encoding="utf-8"))
        sandbox_image_id = approved["images"][SANDBOX_IMAGE_REF]["id"]
        if GIT_IMAGE_REF not in approved["images"]:
            raise KeyError(GIT_IMAGE_REF)
    except Exception as exc:
        approved = {}
        sandbox_image_id = "<missing-sandbox-image>"
        errors.append(f"trusted approved image evidence missing or invalid for broker verification: {exc}")

    if ledger.get("schema_version") != 1:
        errors.append("trusted Docker command broker ledger schema mismatch")
    if ledger.get("broker_authority") != BROKER_AUTHORITY:
        errors.append("trusted Docker command broker authority mismatch")
    if ledger.get("ready_before_candidate") is not True:
        errors.append("trusted Docker command broker was not ready before candidate execution")
    if ledger.get("complete") is not True:
        errors.append("trusted Docker command broker ledger is incomplete")
    if ledger.get("overflow") is not False:
        errors.append("trusted Docker command broker ledger overflowed")
    if ledger.get("broker_error") not in (None, ""):
        errors.append("trusted Docker command broker reported an error")
    if ledger.get("candidate_endpoint") != BROKER_ENDPOINT:
        errors.append("candidate Docker endpoint is not the trusted Unix command broker")
    if ledger.get("direct_daemon_endpoint_exposed") is not False:
        errors.append("raw Docker Engine endpoint was exposed to candidate")

    events = ledger.get("events")
    if not isinstance(events, list) or not events:
        errors.append("trusted Docker command broker ledger has no events")
        events = []
    if len(events) > 8192:
        errors.append("trusted Docker command broker ledger exceeds event limit")

    requests: dict[str, dict[str, Any]] = {}
    responses: dict[str, dict[str, Any]] = {}
    created: set[str] = set()
    for expected_sequence, event in enumerate(events, 1):
        if not isinstance(event, dict):
            errors.append("trusted Docker command broker ledger contains a non-object event")
            continue
        if event.get("sequence") != expected_sequence:
            errors.append("trusted Docker command broker sequence is not contiguous")
        phase = event.get("phase")
        request_id = event.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            errors.append("trusted Docker command broker event lacks request identity")
            continue
        if phase == "request":
            if request_id in requests:
                errors.append("trusted Docker command broker request identity is duplicated")
            requests[request_id] = event
            argv = event.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
                errors.append("trusted Docker command broker request argv is invalid")
                continue
            if event.get("argv_sha256") != _sha256_bytes(_canonical_bytes(argv)):
                errors.append("trusted Docker command broker request argv hash mismatch")
            if event.get("decision") != "ALLOW":
                errors.append("trusted Docker command broker recorded a denied or unknown request")
            if event.get("command_class") not in BROKER_CLASSES:
                errors.append("trusted Docker command broker recorded an unknown command class")
            allowed, expected_class, reason = classify_broker_argv(
                argv,
                git_image=GIT_IMAGE_REF,
                sandbox_image_id=sandbox_image_id,
                canonical_url=CANONICAL_URL,
                created=created,
            )
            if not allowed:
                errors.append(f"trusted Docker command broker ledger contains command outside exact grammar: {reason}")
            if event.get("command_class") != expected_class:
                errors.append("trusted Docker command broker command class mismatch")
            if any(item in {"-H", "--host"} or item.startswith("--host=") for item in argv):
                errors.append("candidate attempted to select a raw Docker Engine endpoint")
            urls = [item for item in argv if "://" in item]
            if any(item != CANONICAL_URL for item in urls):
                errors.append("trusted Docker command broker request contains an unapproved URL")
        elif phase == "response":
            if request_id in responses:
                errors.append("trusted Docker command broker response identity is duplicated")
            responses[request_id] = event
            if not isinstance(event.get("returncode"), int):
                errors.append("trusted Docker command broker response return code is invalid")
            for field in ("stdout_sha256", "stderr_sha256"):
                value = event.get(field)
                if not isinstance(value, str) or len(value) != 64:
                    errors.append(f"trusted Docker command broker response {field} is invalid")
            request = requests.get(request_id)
            if request is not None and event.get("returncode") == 0:
                argv = request.get("argv")
                if isinstance(argv, list) and argv:
                    if argv[0] == "create":
                        names = _option(argv, "--name")
                        if len(names) == 1:
                            created.add(names[0])
                    elif argv[0] == "rm":
                        created.discard(argv[-1])
        else:
            errors.append("trusted Docker command broker event phase is invalid")

    if set(requests) != set(responses):
        errors.append("trusted Docker command broker request/response sequence is incomplete")
    for request_id, request in requests.items():
        response = responses.get(request_id)
        if response is not None and response.get("request_argv_sha256") != request.get("argv_sha256"):
            errors.append("trusted Docker command broker response is not bound to its request")

    if network.get("candidate_network") not in {"internal-only", "none"}:
        errors.append("candidate network classification is invalid")
    if network.get("candidate_network_mode") != "none":
        errors.append("candidate container retained a network path to the nested Docker daemon")
    if network.get("candidate_docker_endpoint") != "TRUSTED_UNIX_COMMAND_BROKER":
        errors.append("candidate Docker endpoint was not the trusted Unix command broker")
    if network.get("candidate_direct_daemon_access") is not False:
        errors.append("candidate retained direct raw Docker Engine access")
    if network.get("broker_socket_mounted") is not True:
        errors.append("trusted broker socket mount was not observed")
    if network.get("nested_daemon_egress") is not True:
        errors.append("nested daemon egress required for controlled acquisition was not established")
    if observation.get("candidate_direct_daemon_access") is not False:
        errors.append("execution observation does not reject direct daemon access")
    if observation.get("docker_command_broker_authority") != BROKER_AUTHORITY:
        errors.append("execution observation lacks trusted Docker command broker authority")

    ignored = {
        "docker-command-ledger.json",
        "network-observation.json",
        "observation-manifest.json",
        "approved-nested-images.json",
        "files-sha256.json",
    }
    for path in execution_dir.rglob("*.json"):
        relative = path.relative_to(execution_dir).as_posix()
        if relative in ignored or relative.startswith("results/"):
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if _contains_raw_daemon_claim(value):
            errors.append("raw Docker Engine API activity exists outside trusted broker ledger")

    return {
        "verified": not errors,
        "events": len(events),
        "requests": len(requests),
        "responses": len(responses),
        "errors": sorted(set(errors)),
    }


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


def _load_baseline_fixture_module():
    completed = subprocess.run(
        ["git", "show", f"{BASELINE_SHA}:{BASELINE_TEST_PATH}"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    temporary = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".py", prefix="p1-verifier-baseline-", delete=False
    )
    try:
        temporary.write(completed.stdout)
        temporary.close()
        path = Path(temporary.name)
        spec = importlib.util.spec_from_file_location("p1_verifier_baseline_fixture", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load baseline verifier fixture")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.ROOT = ROOT
        module.WORKFLOW = WORKFLOW
        module.VERIFIER = ROOT / "tools/p1_verifier/verify_candidate.py"
        module.ACCEPTANCE = ACCEPTANCE
        return module, path
    except Exception:
        Path(temporary.name).unlink(missing_ok=True)
        raise


def _write_valid_broker(fixture: Any, baseline: Any) -> None:
    argv = ["version", "--format", "{{.Server.Version}}"]
    argv_hash = _sha256_bytes(_canonical_bytes(argv))
    ledger = {
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
    }
    baseline._write_json(fixture.execution / "docker-command-ledger.json", ledger)
    network_path = fixture.execution / "network-observation.json"
    network = json.loads(network_path.read_text())
    network.update(
        candidate_network="internal-only",
        candidate_network_mode="none",
        candidate_docker_endpoint="TRUSTED_UNIX_COMMAND_BROKER",
        candidate_direct_daemon_access=False,
        broker_socket_mounted=True,
        nested_daemon_egress=True,
    )
    baseline._write_json(network_path, network)
    observation_path = fixture.execution / "observation-manifest.json"
    observation = json.loads(observation_path.read_text())
    observed_environment = [
        name for name in observation.get("candidate_environment_names", [])
        if name != "DOCKER_HOST"
    ]
    observation.update(
        candidate_direct_daemon_access=False,
        docker_command_broker_authority=BROKER_AUTHORITY,
        candidate_environment_names=observed_environment,
    )
    baseline._write_json(observation_path, observation)
    baseline._hash_manifest(fixture.execution)


class DockerCommandBrokerTests(unittest.TestCase):
    def _fixture(self):
        baseline, module_path = _load_baseline_fixture_module()
        temporary = tempfile.TemporaryDirectory()
        fixture = baseline.VerifierFixture(Path(temporary.name))
        return baseline, module_path, temporary, fixture

    def test_workflow_removes_direct_raw_docker_endpoint(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("TRUSTED_UNIX_COMMAND_BROKER", text)
        self.assertIn("docker-command-ledger.json", text)
        self.assertIn("--network none", text)
        self.assertIn("/broker/docker-command.sock", text)
        self.assertNotIn("--env DOCKER_HOST=tcp://p1-dind:2375", text)
        self.assertIn("trusted/tests/test_p1_verifier.py --verify-broker", text)

    def _network_git_argv(self) -> list[str]:
        commit = "1" * 40
        return [
            "run", "--rm", "--platform", "linux/amd64", "--network", "bridge",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "128", "--memory", "512m", "--cpus", "1",
            "--user", "1000:1000", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--workdir", "/executor-run",
            "--mount", "type=bind,src=/runs/pilot-run,dst=/executor-run,rw",
            "--entrypoint", "/bin/busybox", "git-image",
            "env", "-i", *GIT_ENVIRONMENT, "/usr/bin/git", *FETCH_CONFIG,
            "--git-dir", "/executor-run/acquisition/repository.git", "fetch",
            "--no-tags", "--no-recurse-submodules", "--depth=1", CANONICAL_URL,
            f"+{commit}:refs/executor/input",
        ]

    def _fixture_create_argv(self) -> list[str]:
        return [
            "create", "--name", "cos-executor-abcdef123456", "--network", "none",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "16", "--memory", "64m", "--cpus", "1.0",
            "--user", "65534:65534", "--env", "HOME=/nonexistent",
            "--workdir", "/source",
            "--mount", "type=bind,src=/candidate/tests/fixtures/sandbox,dst=/source,readonly",
            "--tmpfs", "/workspace:rw,nosuid,nodev,size=8m,mode=1777",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
            "sandbox-image-id", "python", "/source/sandbox_fixture.py", "read_source",
        ]

    def test_classifier_accepts_exact_pinned_fetch(self):
        allowed, command_class, reason = classify_broker_argv(
            self._network_git_argv(),
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertTrue(allowed, reason)
        self.assertEqual(command_class, "run-git-network")

    def test_classifier_rejects_git_alias_fetch_bypass(self):
        argv = self._network_git_argv()
        git_index = argv.index("/usr/bin/git")
        argv[git_index + 1:git_index + 1] = ["-c", "alias.fetch=!sh -c 'id'"]
        allowed, _, reason = classify_broker_argv(
            argv,
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertFalse(allowed)
        self.assertIn("exact pinned fetch", reason)

    def test_classifier_rejects_privileged_volume_and_entrypoint_bypasses(self):
        attacks = []
        privileged = self._network_git_argv()
        privileged.insert(privileged.index("git-image"), "--privileged=true")
        attacks.append(privileged)
        volume = self._network_git_argv()
        volume[volume.index("git-image"):volume.index("git-image")] = ["--volume", "/candidate:/host"]
        attacks.append(volume)
        entrypoint = self._fixture_create_argv()
        entrypoint[entrypoint.index("sandbox-image-id"):entrypoint.index("sandbox-image-id")] = ["--entrypoint", "/bin/sh"]
        attacks.append(entrypoint)
        for argv in attacks:
            allowed, _, _ = classify_broker_argv(
                argv,
                git_image="git-image",
                sandbox_image_id="sandbox-image-id",
                canonical_url=CANONICAL_URL,
                created=set(),
            )
            self.assertFalse(allowed, argv)

    def test_classifier_preserves_exact_sandbox_fixture_command(self):
        allowed, command_class, reason = classify_broker_argv(
            self._fixture_create_argv(),
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertTrue(allowed, reason)
        self.assertEqual(command_class, "create-sandbox")

    def test_classifier_rejects_mount_traversal(self):
        argv = self._fixture_create_argv()
        index = argv.index("type=bind,src=/candidate/tests/fixtures/sandbox,dst=/source,readonly")
        argv[index] = "type=bind,src=/candidate/../runs/attack,dst=/source,readonly"
        allowed, _, reason = classify_broker_argv(
            argv,
            git_image="git-image",
            sandbox_image_id="sandbox-image-id",
            canonical_url=CANONICAL_URL,
            created=set(),
        )
        self.assertFalse(allowed)
        self.assertIn("mount", reason)

    def test_broker_ledger_rejects_git_alias_bypass(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            path = fixture.execution / "docker-command-ledger.json"
            ledger = json.loads(path.read_text())
            argv = self._network_git_argv()
            argv[argv.index("git-image")] = GIT_IMAGE_REF
            git_index = argv.index("/usr/bin/git")
            argv[git_index + 1:git_index + 1] = ["-c", "alias.fetch=!sh -c 'id'"]
            ledger["events"][0].update(
                argv=argv,
                argv_sha256=_sha256_bytes(_canonical_bytes(argv)),
                command_class="run-git-network",
            )
            ledger["events"][1]["request_argv_sha256"] = ledger["events"][0]["argv_sha256"]
            baseline._write_json(path, ledger)
            baseline._hash_manifest(fixture.execution)
            summary = verify_broker_evidence(fixture.execution)
            self.assertFalse(summary["verified"], summary)
            self.assertTrue(any("exact grammar" in error for error in summary["errors"]), summary)
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_valid_broker_evidence_preserves_authoritative_pass(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
            self.assertEqual(report["authoritative_result"], "PASS", report)
            gate = apply_broker_gate(
                execution_dir=fixture.execution,
                gate_path=fixture.output / "authoritative-final-gate.json",
                output_path=fixture.output / "docker-command-broker-verification.json",
            )
            self.assertEqual(gate["authoritative_result"], "PASS", gate)
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_missing_broker_ledger_fails_closed(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            baseline._hash_manifest(fixture.execution)
            summary = verify_broker_evidence(fixture.execution)
            self.assertFalse(summary["verified"], summary)
            self.assertTrue(any("ledger missing" in error for error in summary["errors"]))
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_incomplete_broker_sequence_fails_closed(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            path = fixture.execution / "docker-command-ledger.json"
            ledger = json.loads(path.read_text())
            ledger["events"] = ledger["events"][:1]
            baseline._write_json(path, ledger)
            baseline._hash_manifest(fixture.execution)
            summary = verify_broker_evidence(fixture.execution)
            self.assertFalse(summary["verified"], summary)
            self.assertTrue(any("incomplete" in error for error in summary["errors"]))
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_unknown_or_denied_broker_command_fails_closed(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            path = fixture.execution / "docker-command-ledger.json"
            ledger = json.loads(path.read_text())
            ledger["events"][0]["decision"] = "DENY"
            ledger["events"][0]["command_class"] = "raw-api"
            baseline._write_json(path, ledger)
            baseline._hash_manifest(fixture.execution)
            summary = verify_broker_evidence(fixture.execution)
            self.assertFalse(summary["verified"], summary)
            self.assertTrue(any("denied or unknown" in error for error in summary["errors"]))
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)

    def test_untracked_nested_daemon_registry_request_is_rejected(self):
        baseline, module_path, temporary, fixture = self._fixture()
        try:
            _write_valid_broker(fixture, baseline)
            baseline._write_json(
                fixture.execution / "untracked-docker-api-request.json",
                {
                    "method": "GET",
                    "path": "/distribution/attacker.example/image/json",
                    "daemon_network_request": True,
                    "container_or_image_event": False,
                },
            )
            baseline._hash_manifest(fixture.execution)
            report = verify(
                acceptance_path=fixture.acceptance,
                controller_dir=fixture.controller,
                execution_dir=fixture.execution,
                candidate_dir=fixture.candidate,
                source_anchor_root=fixture.source_anchors,
                output_dir=fixture.output,
            )
            self.assertEqual(report["authoritative_result"], "PASS", report)
            gate = apply_broker_gate(
                execution_dir=fixture.execution,
                gate_path=fixture.output / "authoritative-final-gate.json",
                output_path=fixture.output / "docker-command-broker-verification.json",
            )
            self.assertEqual(gate["authoritative_result"], "FAIL", gate)
            self.assertTrue(
                any("outside trusted broker ledger" in error for error in gate["errors"]),
                gate["errors"],
            )
        finally:
            temporary.cleanup()
            module_path.unlink(missing_ok=True)


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
