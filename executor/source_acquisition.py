"""Controlled source acquisition for the Executor PR #29 MVP.

ADR-001 supports exactly one input model: acquire one allowlisted repository at
one full commit through HTTPS in a digest-pinned Git container. A local
checkout, arbitrary URL, bundle, object store, SSH transport, or host Git
fallback is never accepted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Mapping, Protocol, Sequence

INPUT_MODEL = "CONTROLLED_HTTPS_FETCH_V1"
ALLOWED_HOST = "github.com"
ALLOWED_REPOSITORY = "litrgratis-pixel/executor-pilot-target"
CANONICAL_REPOSITORY_URL = (
    "https://github.com/litrgratis-pixel/executor-pilot-target.git"
)
PILOT_ALLOWED_PATH = "project_registry/registry.py"

PINNED_GIT_IMAGE = (
    "alpine/git@sha256:"
    "0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd"
)
PINNED_GIT_PLATFORM = "linux/amd64"
PINNED_GIT_BINARY = "/usr/bin/git"
PINNED_GIT_VERSION = "git version 2.54.0"
CONTAINER_RUN_ROOT = PurePosixPath("/executor-run")

_FULL_OID = re.compile(r"\A[0-9a-f]{40}\Z")
_RUN_ID = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class SourceAcquisitionError(RuntimeError):
    pass


class InputModelViolation(SourceAcquisitionError):
    pass


class ToolchainMismatch(SourceAcquisitionError):
    pass


class AcquisitionCommandError(SourceAcquisitionError):
    pass


class ObjectIdentityError(SourceAcquisitionError):
    pass


class OriginAnchorError(SourceAcquisitionError):
    pass


class PathBoundaryError(SourceAcquisitionError):
    pass


@dataclass(frozen=True)
class SourceAcquisitionRequest:
    run_id: str
    repository: str
    commit: str
    contract_blob: str
    runs_root: Path
    contract_path: str = "PILOT_CONTRACT.md"


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    timed_out: bool = False


class CommandRunner(Protocol):
    def run(self, argv: Sequence[str], *, timeout_seconds: int) -> CommandResult:
        ...


class SubprocessCommandRunner:
    """Run argv directly with no shell and no inherited Git environment."""

    def run(self, argv: Sequence[str], *, timeout_seconds: int) -> CommandResult:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
                env=_minimal_host_environment(),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                argv=tuple(map(str, argv)),
                returncode=124,
                stdout=_to_text(exc.stdout),
                stderr=_to_text(exc.stderr),
                duration_seconds=time.monotonic() - started,
                timed_out=True,
            )
        return CommandResult(
            argv=tuple(map(str, argv)),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=time.monotonic() - started,
        )


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    kind: str
    mode: int
    sha256: str | None = None
    symlink_target: str | None = None


@dataclass(frozen=True)
class SourceAcquisitionResult:
    input_model: str
    repository: str
    canonical_url: str
    commit: str
    root_tree: str
    contract_path: str
    contract_blob: str
    run_dir: Path
    git_dir: Path
    source_dir: Path
    manifest_path: Path
    evidence_path: Path
    toolchain_image: str
    toolchain_platform: str
    git_binary: str
    git_version: str


@dataclass
class _Evidence:
    schema: str = "executor.source-acquisition-evidence.v1"
    input_model: str = INPUT_MODEL
    request: dict[str, str] = field(default_factory=dict)
    origin_anchor: dict[str, object] = field(default_factory=dict)
    toolchain: dict[str, str] = field(default_factory=dict)
    commands: list[dict[str, object]] = field(default_factory=list)
    object_identity: dict[str, object] = field(default_factory=dict)
    manifest: dict[str, object] = field(default_factory=dict)
    outcome: str = "IN_PROGRESS"
    error: str | None = None


class ControlledHttpsSourceAcquirer:
    """Acquire the sole MVP repository into an Executor-owned run directory."""

    def __init__(
        self,
        runner: CommandRunner | None = None,
        *,
        docker_binary: str = "docker",
        command_timeout_seconds: int = 180,
    ) -> None:
        self._runner = runner or SubprocessCommandRunner()
        self._docker_binary = docker_binary
        self._timeout = command_timeout_seconds
        self._evidence: _Evidence | None = None
        self._evidence_path: Path | None = None

    def acquire(self, request: SourceAcquisitionRequest) -> SourceAcquisitionResult:
        request = validate_request(request)
        paths = _prepare_run_paths(request)
        self._evidence_path = paths["evidence"] / "source_acquisition.json"
        self._evidence = _Evidence(
            request={
                "run_id": request.run_id,
                "repository": request.repository,
                "commit": request.commit,
                "contract_blob": request.contract_blob,
                "contract_path": request.contract_path,
            },
            origin_anchor={
                "host": ALLOWED_HOST,
                "repository": ALLOWED_REPOSITORY,
                "canonical_url": CANONICAL_REPOSITORY_URL,
                "transport": "https",
                "redirect_policy": "forbidden",
                "local_checkout_used": False,
                "user_supplied_url_used": False,
            },
            toolchain={
                "image": PINNED_GIT_IMAGE,
                "platform": PINNED_GIT_PLATFORM,
                "binary": PINNED_GIT_BINARY,
                "expected_version": PINNED_GIT_VERSION,
            },
        )
        self._flush()

        try:
            self._verify_toolchain(paths["run_dir"])
            self._initialize_repository(paths)
            self._fetch_exact_commit(paths, request.commit)
            identity = self._verify_identity(paths, request)
            self._create_source_worktree(paths, request.commit)
            _require_regular_file(paths["source_dir"], request.contract_path)
            _require_regular_file(paths["source_dir"], PILOT_ALLOWED_PATH)

            entries = build_manifest(paths["source_dir"])
            manifest_path = paths["evidence"] / "source_manifest.json"
            _atomic_write_json(
                manifest_path,
                {
                    "schema": "executor.source-manifest.v1",
                    "root": str(paths["source_dir"]),
                    "entries": [asdict(entry) for entry in entries],
                },
            )
            assert self._evidence is not None
            self._evidence.object_identity = identity
            self._evidence.manifest = {
                "path": str(manifest_path),
                "entry_count": len(entries),
                "sha256": sha256_file(manifest_path),
            }
            self._evidence.outcome = "ACQUIRED_REVIEW_REQUIRED"
            self._flush()
            return SourceAcquisitionResult(
                input_model=INPUT_MODEL,
                repository=request.repository,
                canonical_url=CANONICAL_REPOSITORY_URL,
                commit=request.commit,
                root_tree=str(identity["root_tree"]),
                contract_path=request.contract_path,
                contract_blob=request.contract_blob,
                run_dir=paths["run_dir"],
                git_dir=paths["git_dir"],
                source_dir=paths["source_dir"],
                manifest_path=manifest_path,
                evidence_path=self._evidence_path,
                toolchain_image=PINNED_GIT_IMAGE,
                toolchain_platform=PINNED_GIT_PLATFORM,
                git_binary=PINNED_GIT_BINARY,
                git_version=PINNED_GIT_VERSION,
            )
        except Exception as exc:
            self._record_failure(exc)
            _safe_remove(paths["source_dir"])
            _safe_remove(paths["acquisition"])
            raise

    def _verify_toolchain(self, run_dir: Path) -> None:
        inspected = self._host(
            [
                self._docker_binary,
                "image",
                "inspect",
                "--format",
                "{{json .RepoDigests}}|{{.Os}}/{{.Architecture}}|{{.Id}}",
                PINNED_GIT_IMAGE,
            ],
            "docker-image-inspect",
        )
        fields = inspected.stdout.strip().split("|", 2)
        if len(fields) != 3:
            raise ToolchainMismatch("unexpected Docker image inspect output")
        repo_digests, platform, image_id = fields
        if PINNED_GIT_IMAGE not in repo_digests:
            raise ToolchainMismatch("pinned image digest is absent from RepoDigests")
        if platform != PINNED_GIT_PLATFORM:
            raise ToolchainMismatch(
                f"expected {PINNED_GIT_PLATFORM}, observed {platform}"
            )
        version = self._git(
            run_dir, ["--version"], network="none", label="git-version"
        ).stdout.strip()
        if version != PINNED_GIT_VERSION:
            raise ToolchainMismatch(
                f"expected {PINNED_GIT_VERSION!r}, observed {version!r}"
            )
        assert self._evidence is not None
        self._evidence.toolchain.update(
            image_id=image_id,
            observed_version=version,
        )
        self._flush()

    def _initialize_repository(self, paths: Mapping[str, Path]) -> None:
        git_dir = _container_path(paths["run_dir"], paths["git_dir"])
        self._git(
            paths["run_dir"],
            ["init", "--bare", str(git_dir)],
            network="none",
            label="git-init-bare",
        )
        settings = (
            ("core.hooksPath", "/dev/null"),
            ("core.fsmonitor", "false"),
            ("core.autocrlf", "false"),
            ("core.safecrlf", "true"),
            ("core.attributesFile", "/dev/null"),
            ("commit.gpgSign", "false"),
            ("tag.gpgSign", "false"),
            ("credential.helper", ""),
            ("core.askPass", "/bin/false"),
            ("diff.external", ""),
            ("interactive.diffFilter", ""),
            ("fetch.recurseSubmodules", "false"),
            ("submodule.recurse", "false"),
            ("http.followRedirects", "false"),
            ("user.name", "Creative OS Executor"),
            ("user.email", "executor@localhost"),
        )
        for key, value in settings:
            self._git(
                paths["run_dir"],
                ["--git-dir", str(git_dir), "config", "--local", key, value],
                network="none",
                label=f"git-config:{key}",
            )

    def _fetch_exact_commit(self, paths: Mapping[str, Path], commit: str) -> None:
        git_dir = _container_path(paths["run_dir"], paths["git_dir"])
        self._git(
            paths["run_dir"],
            [
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
                "--git-dir", str(git_dir),
                "fetch",
                "--no-tags",
                "--no-recurse-submodules",
                "--depth=1",
                CANONICAL_REPOSITORY_URL,
                f"+{commit}:refs/executor/input",
            ],
            network="bridge",
            label="git-fetch-pinned-commit",
        )

    def _verify_identity(
        self,
        paths: Mapping[str, Path],
        request: SourceAcquisitionRequest,
    ) -> dict[str, object]:
        git_dir = _container_path(paths["run_dir"], paths["git_dir"])
        common = ["--git-dir", str(git_dir)]
        fetch_head = self._git(
            paths["run_dir"],
            [*common, "rev-parse", "--verify", "FETCH_HEAD^{commit}"],
            network="none",
            label="verify-fetch-head",
        ).stdout.strip()
        commit = self._git(
            paths["run_dir"],
            [*common, "rev-parse", "--verify", "refs/executor/input^{commit}"],
            network="none",
            label="verify-commit",
        ).stdout.strip()
        if fetch_head != request.commit or commit != request.commit:
            raise ObjectIdentityError("fetched commit does not match pinned commit")
        root_tree = self._git(
            paths["run_dir"],
            [*common, "rev-parse", f"{request.commit}^{{tree}}"],
            network="none",
            label="verify-root-tree",
        ).stdout.strip()
        contract_blob = self._git(
            paths["run_dir"],
            [*common, "rev-parse", f"{request.commit}:{request.contract_path}"],
            network="none",
            label="verify-contract-blob",
        ).stdout.strip()
        if contract_blob != request.contract_blob:
            raise ObjectIdentityError("PILOT_CONTRACT.md blob mismatch")
        self._git(
            paths["run_dir"],
            [*common, "fsck", "--strict", "--full", "--no-reflogs"],
            network="none",
            label="git-fsck-strict",
        )
        return {
            "fetch_head": fetch_head,
            "commit": commit,
            "root_tree": root_tree,
            "contract_path": request.contract_path,
            "contract_blob": contract_blob,
            "fsck_strict": True,
        }

    def _create_source_worktree(
        self,
        paths: Mapping[str, Path],
        commit: str,
    ) -> None:
        git_dir = _container_path(paths["run_dir"], paths["git_dir"])
        source = _container_path(paths["run_dir"], paths["source_dir"])
        self._git(
            paths["run_dir"],
            [
                "-c", "filter.lfs.process=",
                "-c", "filter.lfs.smudge=cat",
                "-c", "filter.lfs.clean=cat",
                "-c", "filter.lfs.required=false",
                "--git-dir", str(git_dir),
                "worktree", "add", "--detach", str(source), commit,
            ],
            network="none",
            label="git-worktree-add",
        )
        status = self._git(
            paths["run_dir"],
            ["-C", str(source), "status", "--porcelain=v1", "--untracked-files=all"],
            network="none",
            label="verify-controlled-worktree-clean",
        )
        if status.stdout:
            raise ObjectIdentityError("controlled source worktree is not clean")

    def _host(self, argv: Sequence[str], label: str) -> CommandResult:
        result = self._runner.run(argv, timeout_seconds=self._timeout)
        self._record(label, result, "host-docker-client")
        _require_success(label, result)
        return result

    def _git(
        self,
        run_dir: Path,
        args: Sequence[str],
        *,
        network: str,
        label: str,
    ) -> CommandResult:
        result = self._runner.run(
            build_git_container_argv(
                docker_binary=self._docker_binary,
                run_dir=run_dir,
                git_args=args,
                network=network,
            ),
            timeout_seconds=self._timeout,
        )
        self._record(label, result, f"git-control-plane:{network}")
        _require_success(label, result)
        return result

    def _record(
        self,
        label: str,
        result: CommandResult,
        boundary: str,
    ) -> None:
        if self._evidence is None:
            return
        self._evidence.commands.append(
            {
                "label": label,
                "boundary": boundary,
                "argv": list(result.argv),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "duration_seconds": result.duration_seconds,
                "timed_out": result.timed_out,
            }
        )
        self._flush()

    def _record_failure(self, exc: Exception) -> None:
        if self._evidence is None:
            return
        self._evidence.outcome = "ACQUISITION_BLOCKED"
        self._evidence.error = f"{type(exc).__name__}: {exc}"
        self._flush()

    def _flush(self) -> None:
        if self._evidence is not None and self._evidence_path is not None:
            _atomic_write_json(self._evidence_path, asdict(self._evidence))


class ControlledGit:
    """Network-disabled Git wrapper confined to one acquired run directory."""

    _ALLOWED = frozenset(
        {
            "add",
            "cat-file",
            "commit",
            "diff",
            "ls-tree",
            "rev-list",
            "rev-parse",
            "status",
            "switch",
            "worktree",
        }
    )

    def __init__(
        self,
        result: SourceAcquisitionResult,
        runner: CommandRunner | None = None,
        *,
        docker_binary: str = "docker",
        command_timeout_seconds: int = 120,
    ) -> None:
        self.result = result
        self._runner = runner or SubprocessCommandRunner()
        self._docker_binary = docker_binary
        self._timeout = command_timeout_seconds

    def run(self, git_args: Sequence[str]) -> CommandResult:
        _validate_controlled_git_args(git_args, self.result.run_dir)
        translated = _translate_controlled_git_args(git_args, self.result.run_dir)
        subcommand = _git_subcommand(translated)
        if subcommand not in self._ALLOWED:
            raise InputModelViolation(
                f"Git subcommand {subcommand!r} is outside the pilot allowlist"
            )
        result = self._runner.run(
            build_git_container_argv(
                docker_binary=self._docker_binary,
                run_dir=self.result.run_dir,
                git_args=translated,
                network="none",
            ),
            timeout_seconds=self._timeout,
        )
        _require_success(f"controlled git {subcommand}", result)
        return result


def validate_request(request: SourceAcquisitionRequest) -> SourceAcquisitionRequest:
    if request.repository != ALLOWED_REPOSITORY:
        raise InputModelViolation(
            f"repository must be exactly {ALLOWED_REPOSITORY!r}"
        )
    if not _FULL_OID.fullmatch(request.commit):
        raise InputModelViolation("commit must be a full lowercase 40-hex Git OID")
    if not _FULL_OID.fullmatch(request.contract_blob):
        raise InputModelViolation(
            "contract_blob must be a full lowercase 40-hex Git blob OID"
        )
    if not _RUN_ID.fullmatch(request.run_id):
        raise InputModelViolation("run_id contains unsupported characters")
    if request.contract_path != "PILOT_CONTRACT.md":
        raise InputModelViolation("contract_path must be exactly PILOT_CONTRACT.md")
    runs_root = request.runs_root.expanduser()
    if not runs_root.is_absolute():
        raise InputModelViolation("runs_root must be an absolute path")
    _reject_symlink_components(runs_root)
    _reject_repository_ancestor(runs_root)
    return SourceAcquisitionRequest(
        run_id=request.run_id,
        repository=request.repository,
        commit=request.commit,
        contract_blob=request.contract_blob,
        runs_root=runs_root.resolve(strict=False),
        contract_path=request.contract_path,
    )


def build_git_container_argv(
    *,
    docker_binary: str,
    run_dir: Path,
    git_args: Sequence[str],
    network: str,
) -> list[str]:
    if network not in {"none", "bridge"}:
        raise ValueError("network must be 'none' or 'bridge'")
    run_dir = run_dir.resolve(strict=False)
    if not run_dir.is_absolute():
        raise PathBoundaryError("run_dir must be absolute")
    _reject_control_characters(str(run_dir))
    if "," in str(run_dir):
        raise PathBoundaryError("commas are forbidden in Docker mount paths")
    environment = [
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
    uid = os.getuid() if hasattr(os, "getuid") else 65532
    gid = os.getgid() if hasattr(os, "getgid") else 65532
    return [
        docker_binary,
        "run",
        "--rm",
        "--label", "creative-os-executor-source-git=true",
        "--label", f"creative-os-executor-source-run={run_dir.name}",
        "--platform", PINNED_GIT_PLATFORM,
        "--network", network,
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=128",
        "--memory=512m",
        "--cpus=1",
        "--user", f"{uid}:{gid}",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864",
        "--mount", f"type=bind,src={run_dir},dst=/executor-run,rw",
        "--workdir", "/executor-run",
        "--entrypoint", "/bin/busybox",
        PINNED_GIT_IMAGE,
        "env", "-i", *environment,
        PINNED_GIT_BINARY,
        *map(str, git_args),
    ]


def load_source_acquisition_result(
    run_dir: str | Path,
) -> SourceAcquisitionResult:
    root = Path(run_dir).resolve(strict=True)
    evidence_path = root / "evidence" / "source_acquisition.json"
    manifest_path = root / "evidence" / "source_manifest.json"
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise InputModelViolation(f"invalid acquisition evidence: {exc}") from exc
    if evidence.get("schema") != "executor.source-acquisition-evidence.v1":
        raise InputModelViolation("unsupported acquisition evidence schema")
    if evidence.get("outcome") != "ACQUIRED_REVIEW_REQUIRED":
        raise InputModelViolation("acquisition evidence is not successful")

    request = evidence.get("request") or {}
    origin = evidence.get("origin_anchor") or {}
    toolchain = evidence.get("toolchain") or {}
    identity = evidence.get("object_identity") or {}
    if request.get("repository") != ALLOWED_REPOSITORY:
        raise InputModelViolation("evidence repository is not allowlisted")
    if origin.get("canonical_url") != CANONICAL_REPOSITORY_URL:
        raise OriginAnchorError("canonical origin anchor mismatch")
    if origin.get("local_checkout_used") is not False:
        raise OriginAnchorError("local checkout use is forbidden")
    if origin.get("user_supplied_url_used") is not False:
        raise OriginAnchorError("user supplied URL use is forbidden")
    if toolchain.get("image") != PINNED_GIT_IMAGE:
        raise ToolchainMismatch("evidence image mismatch")
    if toolchain.get("platform") != PINNED_GIT_PLATFORM:
        raise ToolchainMismatch("evidence platform mismatch")
    if toolchain.get("binary") != PINNED_GIT_BINARY:
        raise ToolchainMismatch("evidence Git binary mismatch")
    if toolchain.get("observed_version") != PINNED_GIT_VERSION:
        raise ToolchainMismatch("evidence Git version mismatch")

    commit = str(request.get("commit", ""))
    contract_blob = str(request.get("contract_blob", ""))
    root_tree = str(identity.get("root_tree", ""))
    if not _FULL_OID.fullmatch(commit):
        raise ObjectIdentityError("invalid commit in evidence")
    if not _FULL_OID.fullmatch(contract_blob):
        raise ObjectIdentityError("invalid contract blob in evidence")
    if not _FULL_OID.fullmatch(root_tree):
        raise ObjectIdentityError("invalid root tree in evidence")

    git_dir = root / "acquisition" / "repository.git"
    source_dir = root / "source"
    for path in (git_dir, source_dir, manifest_path):
        _assert_within(root, path)
    if not git_dir.is_dir() or not source_dir.is_dir() or not manifest_path.is_file():
        raise InputModelViolation("controlled acquisition paths are incomplete")
    manifest = evidence.get("manifest") or {}
    if manifest.get("sha256") != sha256_file(manifest_path):
        raise ObjectIdentityError("source manifest hash mismatch")
    return SourceAcquisitionResult(
        input_model=INPUT_MODEL,
        repository=ALLOWED_REPOSITORY,
        canonical_url=CANONICAL_REPOSITORY_URL,
        commit=commit,
        root_tree=root_tree,
        contract_path=str(request.get("contract_path", "")),
        contract_blob=contract_blob,
        run_dir=root,
        git_dir=git_dir,
        source_dir=source_dir,
        manifest_path=manifest_path,
        evidence_path=evidence_path,
        toolchain_image=PINNED_GIT_IMAGE,
        toolchain_platform=PINNED_GIT_PLATFORM,
        git_binary=PINNED_GIT_BINARY,
        git_version=PINNED_GIT_VERSION,
    )


def verify_manifest_unchanged(result: SourceAcquisitionResult) -> None:
    try:
        expected = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ObjectIdentityError(f"cannot read source manifest: {exc}") from exc
    if expected.get("schema") != "executor.source-manifest.v1":
        raise ObjectIdentityError("unsupported source manifest schema")
    actual = [asdict(entry) for entry in build_manifest(result.source_dir)]
    if expected.get("entries") != actual:
        raise ObjectIdentityError("controlled source changed after acquisition")


def build_manifest(root: Path) -> list[ManifestEntry]:
    root = root.resolve(strict=True)
    entries: list[ManifestEntry] = []
    for path in sorted(
        root.rglob("*"),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative_path = path.relative_to(root)
        if relative_path.parts and relative_path.parts[0] == ".git":
            continue
        relative = relative_path.as_posix()
        metadata = path.lstat()
        mode = stat.S_IMODE(metadata.st_mode)
        if path.is_symlink():
            entries.append(
                ManifestEntry(
                    path=relative,
                    kind="symlink",
                    mode=mode,
                    symlink_target=os.readlink(path),
                )
            )
        elif path.is_file():
            entries.append(
                ManifestEntry(
                    path=relative,
                    kind="file",
                    mode=mode,
                    sha256=sha256_file(path),
                )
            )
        elif path.is_dir():
            entries.append(
                ManifestEntry(path=relative, kind="directory", mode=mode)
            )
        else:
            raise ObjectIdentityError(
                f"unsupported filesystem entry: {relative}"
            )
    return entries


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _prepare_run_paths(
    request: SourceAcquisitionRequest,
) -> dict[str, Path]:
    request.runs_root.mkdir(parents=True, exist_ok=True)
    _reject_symlink_components(request.runs_root)
    run_dir = request.runs_root / request.run_id
    if run_dir.exists():
        raise InputModelViolation(f"run directory already exists: {run_dir}")
    run_dir.mkdir(mode=0o700)
    paths = {
        "run_dir": run_dir,
        "acquisition": run_dir / "acquisition",
        "git_dir": run_dir / "acquisition" / "repository.git",
        "source_dir": run_dir / "source",
        "isolated_home": run_dir / "isolated-home",
        "isolated_xdg": run_dir / "isolated-xdg",
        "evidence": run_dir / "evidence",
    }
    for name in ("acquisition", "isolated_home", "isolated_xdg", "evidence"):
        paths[name].mkdir(mode=0o700)
    for path in paths.values():
        _assert_within(run_dir, path)
    return paths


def _validate_controlled_git_args(
    git_args: Sequence[str],
    run_dir: Path,
) -> None:
    if not git_args:
        raise InputModelViolation("empty Git command")
    args = list(map(str, git_args))
    subcommand = _git_subcommand(args)
    if subcommand in {
        "clone", "config", "fetch", "pull", "push",
        "ls-remote", "remote", "submodule",
    }:
        raise InputModelViolation(f"forbidden Git operation: {subcommand}")

    before_subcommand = True
    index = 0
    while index < len(args):
        argument = args[index]
        _reject_control_characters(argument)
        if before_subcommand and argument == subcommand:
            before_subcommand = False
            index += 1
            continue
        if before_subcommand and (
            argument == "-c"
            or (argument.startswith("-c") and argument != "-C")
            or argument == "--config-env"
            or argument.startswith("--config-env=")
            or argument == "--exec-path"
            or argument.startswith("--exec-path=")
        ):
            raise InputModelViolation(
                f"caller-controlled Git configuration is forbidden: {argument}"
            )
        if argument in {"--ext-diff", "--textconv", "--no-index"}:
            raise InputModelViolation(f"unsafe Git option is forbidden: {argument}")
        if argument.startswith(
            ("http://", "https://", "ssh://", "git://", "file://", "ext::")
        ):
            raise InputModelViolation("URLs are forbidden after acquisition")
        if argument in {"-C", "--git-dir", "--work-tree"}:
            if index + 1 >= len(args):
                raise InputModelViolation(f"missing path after {argument}")
            _validate_controlled_path(args[index + 1], run_dir)
            index += 2
            continue
        if argument.startswith("--git-dir=") or argument.startswith("--work-tree="):
            _validate_controlled_path(argument.split("=", 1)[1], run_dir)
            index += 1
            continue
        if not argument.startswith("-"):
            path = Path(argument)
            if path.is_absolute():
                _assert_within(run_dir, path)
            elif "/" in argument and ".." in path.parts:
                raise PathBoundaryError("relative path traversal is forbidden")
        index += 1


def _translate_controlled_git_args(
    git_args: Sequence[str],
    run_dir: Path,
) -> list[str]:
    translated: list[str] = []
    args = list(map(str, git_args))
    index = 0
    while index < len(args):
        argument = args[index]
        if argument in {"-C", "--git-dir", "--work-tree"}:
            translated.extend(
                [
                    argument,
                    str(_container_path(run_dir, Path(args[index + 1]))),
                ]
            )
            index += 2
            continue
        if argument.startswith("--git-dir=") or argument.startswith("--work-tree="):
            key, value = argument.split("=", 1)
            translated.append(
                f"{key}={_container_path(run_dir, Path(value))}"
            )
            index += 1
            continue
        path = Path(argument)
        if path.is_absolute():
            translated.append(str(_container_path(run_dir, path)))
        else:
            translated.append(argument)
        index += 1
    return translated


def _git_subcommand(git_args: Sequence[str]) -> str:
    args = list(map(str, git_args))
    index = 0
    while index < len(args):
        value = args[index]
        if value in {"-c", "-C", "--git-dir", "--work-tree"}:
            index += 2
            continue
        if value.startswith("--git-dir=") or value.startswith("--work-tree="):
            index += 1
            continue
        if value.startswith("-"):
            index += 1
            continue
        return value
    raise InputModelViolation("Git subcommand was not found")


def _container_path(run_dir: Path, path: Path) -> PurePosixPath:
    _assert_within(run_dir, path)
    relative = path.resolve(strict=False).relative_to(
        run_dir.resolve(strict=False)
    )
    return CONTAINER_RUN_ROOT.joinpath(*relative.parts)


def _validate_controlled_path(value: str, run_dir: Path) -> None:
    path = Path(value)
    if not path.is_absolute():
        raise InputModelViolation("repository control paths must be absolute")
    _assert_within(run_dir, path)


def _assert_within(root: Path, candidate: Path) -> None:
    resolved_root = root.resolve(strict=False)
    resolved_candidate = candidate.resolve(strict=False)
    if (
        resolved_candidate != resolved_root
        and resolved_root not in resolved_candidate.parents
    ):
        raise PathBoundaryError(f"path escapes run directory: {candidate}")


def _reject_repository_ancestor(path: Path) -> None:
    candidate = path.resolve(strict=False)
    for ancestor in (candidate, *candidate.parents):
        marker = ancestor / ".git"
        if marker.exists() or marker.is_symlink():
            raise InputModelViolation(
                f"runs_root must not be inside a Git checkout: {ancestor}"
            )


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise InputModelViolation(
                f"symlink path component is forbidden: {current}"
            )


def _require_regular_file(source_dir: Path, relative: str) -> None:
    candidate = source_dir / relative
    _assert_within(source_dir, candidate)
    try:
        metadata = candidate.lstat()
    except FileNotFoundError as exc:
        raise ObjectIdentityError(
            f"required source path is missing: {relative}"
        ) from exc
    if candidate.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ObjectIdentityError(
            f"required path must be a regular non-symlink file: {relative}"
        )


def _require_success(label: str, result: CommandResult) -> None:
    if result.timed_out:
        raise AcquisitionCommandError(f"{label} timed out")
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise AcquisitionCommandError(
            f"{label} failed with exit code {result.returncode}: {detail}"
        )


def _safe_remove(path: Path) -> None:
    if path.is_symlink():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path, ignore_errors=True)


def _atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _minimal_host_environment() -> dict[str, str]:
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LC_ALL": "C",
    }
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"):
        if name in os.environ:
            environment[name] = os.environ[name]
    return environment


def _reject_control_characters(value: str) -> None:
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise InputModelViolation("control characters are forbidden")


def _to_text(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
