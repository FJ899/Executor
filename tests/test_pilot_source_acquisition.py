from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from executor.pilot_case_001 import CASE_001_CONTRACT
from executor.source_acquisition import (
    ALLOWED_REPOSITORY,
    CANONICAL_REPOSITORY_URL,
    INPUT_MODEL,
    PINNED_GIT_BINARY,
    PINNED_GIT_IMAGE,
    PINNED_GIT_PLATFORM,
    PINNED_GIT_VERSION,
    CommandResult,
    ControlledGit,
    ControlledHttpsSourceAcquirer,
    InputModelViolation,
    ObjectIdentityError,
    PathBoundaryError,
    SourceAcquisitionRequest,
    SourceAcquisitionResult,
    ToolchainMismatch,
    build_git_container_argv,
    build_manifest,
    load_source_acquisition_result,
    validate_request,
    verify_manifest_unchanged,
)

COMMIT = CASE_001_CONTRACT.input_commit
BLOB = CASE_001_CONTRACT.contract_blob_sha
TREE = "1" * 40


class SimulatedDockerRunner:
    def __init__(
        self,
        *,
        observed_blob: str = BLOB,
        version: str = PINNED_GIT_VERSION,
    ):
        self.calls: list[tuple[str, ...]] = []
        self.observed_blob = observed_blob
        self.version = version

    def run(self, argv, *, timeout_seconds):
        del timeout_seconds
        args = tuple(map(str, argv))
        self.calls.append(args)
        joined = " ".join(args)
        if "image inspect" in joined:
            return self._ok(
                args,
                f'["{PINNED_GIT_IMAGE}"]|{PINNED_GIT_PLATFORM}|sha256:toolchain\n',
            )
        if PINNED_GIT_BINARY in args and "--version" in args:
            return self._ok(args, self.version + "\n")
        if "init" in args and "--bare" in args:
            run_dir = self._mounted_run_dir(args)
            (run_dir / "acquisition" / "repository.git").mkdir(
                parents=True, exist_ok=True
            )
        if "rev-parse" in args and "FETCH_HEAD^{commit}" in args:
            return self._ok(args, COMMIT + "\n")
        if "rev-parse" in args and "refs/executor/input^{commit}" in args:
            return self._ok(args, COMMIT + "\n")
        if "rev-parse" in args and f"{COMMIT}^{{tree}}" in args:
            return self._ok(args, TREE + "\n")
        if "rev-parse" in args and f"{COMMIT}:PILOT_CONTRACT.md" in args:
            return self._ok(args, self.observed_blob + "\n")
        if "worktree" in args and "add" in args:
            run_dir = self._mounted_run_dir(args)
            source = run_dir / "source"
            source.mkdir(parents=True, exist_ok=True)
            (source / ".git").write_text("gitdir: controlled\n", encoding="utf-8")
            (source / "PILOT_CONTRACT.md").write_text(
                "contract\n", encoding="utf-8"
            )
            registry = source / "project_registry"
            registry.mkdir()
            (registry / "registry.py").write_text(
                "VALUE = 1\n", encoding="utf-8"
            )
        return self._ok(args, "")

    @staticmethod
    def _ok(args, stdout):
        return CommandResult(argv=args, returncode=0, stdout=stdout)

    @staticmethod
    def _mounted_run_dir(args: tuple[str, ...]) -> Path:
        mount = args[args.index("--mount") + 1]
        prefix = "type=bind,src="
        suffix = ",dst=/executor-run,rw"
        assert mount.startswith(prefix) and mount.endswith(suffix)
        return Path(mount[len(prefix) : -len(suffix)])


class RecordingRunner:
    def __init__(self, result: CommandResult | None = None):
        self.calls = []
        self.result = result

    def run(self, argv, *, timeout_seconds):
        self.calls.append((tuple(argv), timeout_seconds))
        result = self.result or CommandResult(argv=tuple(argv), returncode=0)
        return CommandResult(
            argv=tuple(argv),
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
        )


def request(root: Path, **changes) -> SourceAcquisitionRequest:
    values = {
        "run_id": "case-001",
        "repository": ALLOWED_REPOSITORY,
        "commit": COMMIT,
        "contract_blob": BLOB,
        "runs_root": root,
    }
    values.update(changes)
    return SourceAcquisitionRequest(**values)


class RequestValidationTests(unittest.TestCase):
    def test_accepts_only_exact_repository_and_full_oids(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = validate_request(request(Path(temporary)))
        self.assertEqual(result.repository, ALLOWED_REPOSITORY)
        self.assertEqual(result.commit, COMMIT)

    def test_rejects_different_repository(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(InputModelViolation):
                validate_request(
                    request(Path(temporary), repository="attacker/repository")
                )

    def test_rejects_noncanonical_oids_and_contract_path(self):
        invalid = (
            {"commit": "main"},
            {"commit": COMMIT[:12]},
            {"commit": COMMIT.upper()},
            {"contract_blob": BLOB[:12]},
            {"contract_path": "nested/PILOT_CONTRACT.md"},
        )
        with tempfile.TemporaryDirectory() as temporary:
            for change in invalid:
                with self.subTest(change=change), self.assertRaises(
                    InputModelViolation
                ):
                    validate_request(request(Path(temporary), **change))

    def test_rejects_relative_or_repository_nested_runs_root(self):
        with self.assertRaises(InputModelViolation):
            validate_request(request(Path("relative")))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            with self.assertRaises(InputModelViolation):
                validate_request(request(root / "runs"))


class ContainerCommandTests(unittest.TestCase):
    def test_command_uses_pinned_toolchain_and_isolated_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            argv = build_git_container_argv(
                docker_binary="docker",
                run_dir=Path(temporary),
                git_args=["--version"],
                network="none",
            )
        joined = "\n".join(argv)
        for expected in (
            PINNED_GIT_IMAGE,
            PINNED_GIT_PLATFORM,
            PINNED_GIT_BINARY,
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "GIT_CONFIG_NOSYSTEM=1",
            "GIT_CONFIG_GLOBAL=/dev/null",
            "GIT_ATTR_NOSYSTEM=1",
            "GIT_TERMINAL_PROMPT=0",
            "GIT_ASKPASS=/bin/false",
            "SSH_ASKPASS=/bin/false",
            "GIT_SSH_COMMAND=/bin/false",
            "GIT_LFS_SKIP_SMUDGE=1",
            "GIT_ALLOW_PROTOCOL=https",
        ):
            self.assertIn(expected, argv)
        self.assertNotIn(str(Path.home()), joined)

    def test_fetch_is_the_only_network_enabled_git_command(self):
        runner = SimulatedDockerRunner()
        with tempfile.TemporaryDirectory() as temporary:
            result = ControlledHttpsSourceAcquirer(runner).acquire(
                request(Path(temporary))
            )
        bridge = [
            call
            for call in runner.calls
            if "--network" in call
            and call[call.index("--network") + 1] == "bridge"
        ]
        self.assertEqual(len(bridge), 1)
        self.assertIn("fetch", bridge[0])
        self.assertIn(CANONICAL_REPOSITORY_URL, bridge[0])
        self.assertEqual(result.input_model, INPUT_MODEL)

    def test_fetch_forbids_redirects_credentials_submodules_and_other_protocols(self):
        runner = SimulatedDockerRunner()
        with tempfile.TemporaryDirectory() as temporary:
            ControlledHttpsSourceAcquirer(runner).acquire(request(Path(temporary)))
        fetch = next(call for call in runner.calls if "fetch" in call)
        for expected in (
            "http.followRedirects=false",
            "credential.helper=",
            "core.askPass=/bin/false",
            "protocol.allow=never",
            "protocol.https.allow=always",
            "protocol.file.allow=never",
            "protocol.ext.allow=never",
            "protocol.ssh.allow=never",
            "--no-recurse-submodules",
            f"+{COMMIT}:refs/executor/input",
        ):
            self.assertIn(expected, fetch)


class AcquisitionFlowTests(unittest.TestCase):
    def test_success_produces_manifest_evidence_and_reloadable_result(self):
        runner = SimulatedDockerRunner()
        with tempfile.TemporaryDirectory() as temporary:
            result = ControlledHttpsSourceAcquirer(runner).acquire(
                request(Path(temporary))
            )
            loaded = load_source_acquisition_result(result.run_dir)
            evidence = json.loads(result.evidence_path.read_text())
            manifest = json.loads(result.manifest_path.read_text())
            verify_manifest_unchanged(loaded)
        self.assertEqual(evidence["outcome"], "ACQUIRED_REVIEW_REQUIRED")
        self.assertEqual(evidence["object_identity"]["commit"], COMMIT)
        self.assertEqual(evidence["object_identity"]["contract_blob"], BLOB)
        self.assertFalse(evidence["origin_anchor"]["local_checkout_used"])
        self.assertFalse(evidence["origin_anchor"]["user_supplied_url_used"])
        paths = {entry["path"] for entry in manifest["entries"]}
        self.assertIn("PILOT_CONTRACT.md", paths)
        self.assertIn("project_registry/registry.py", paths)
        self.assertNotIn(".git", paths)

    def test_manifest_tampering_is_blocked(self):
        runner = SimulatedDockerRunner()
        with tempfile.TemporaryDirectory() as temporary:
            result = ControlledHttpsSourceAcquirer(runner).acquire(
                request(Path(temporary))
            )
            (result.source_dir / "project_registry/registry.py").write_text(
                "tampered\n", encoding="utf-8"
            )
            with self.assertRaises(ObjectIdentityError):
                verify_manifest_unchanged(result)

    def test_wrong_blob_fails_closed_retains_failure_and_removes_partial_repo(self):
        runner = SimulatedDockerRunner(observed_blob="f" * 40)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ObjectIdentityError):
                ControlledHttpsSourceAcquirer(runner).acquire(request(root))
            run_dir = root / "case-001"
            evidence = json.loads(
                (run_dir / "evidence/source_acquisition.json").read_text()
            )
            self.assertFalse((run_dir / "source").exists())
            self.assertFalse((run_dir / "acquisition").exists())
        self.assertEqual(evidence["outcome"], "ACQUISITION_BLOCKED")
        self.assertIn("ObjectIdentityError", evidence["error"])

    def test_wrong_git_version_blocks_before_fetch(self):
        runner = SimulatedDockerRunner(version="git version 2.53.0")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ToolchainMismatch):
                ControlledHttpsSourceAcquirer(runner).acquire(
                    request(Path(temporary))
                )
        self.assertFalse(any("fetch" in call for call in runner.calls))


class ControlledGitTests(unittest.TestCase):
    @staticmethod
    def result(root: Path) -> SourceAcquisitionResult:
        run_dir = root / "run"
        git_dir = run_dir / "acquisition/repository.git"
        source_dir = run_dir / "source"
        evidence_dir = run_dir / "evidence"
        git_dir.mkdir(parents=True)
        source_dir.mkdir()
        evidence_dir.mkdir()
        manifest = evidence_dir / "source_manifest.json"
        evidence = evidence_dir / "source_acquisition.json"
        manifest.write_text("{}\n")
        evidence.write_text("{}\n")
        return SourceAcquisitionResult(
            input_model=INPUT_MODEL,
            repository=ALLOWED_REPOSITORY,
            canonical_url=CANONICAL_REPOSITORY_URL,
            commit=COMMIT,
            root_tree=TREE,
            contract_path="PILOT_CONTRACT.md",
            contract_blob=BLOB,
            run_dir=run_dir,
            git_dir=git_dir,
            source_dir=source_dir,
            manifest_path=manifest,
            evidence_path=evidence,
            toolchain_image=PINNED_GIT_IMAGE,
            toolchain_platform=PINNED_GIT_PLATFORM,
            git_binary=PINNED_GIT_BINARY,
            git_version=PINNED_GIT_VERSION,
        )

    def test_post_acquisition_git_is_network_disabled_and_paths_are_translated(self):
        runner = RecordingRunner()
        with tempfile.TemporaryDirectory() as temporary:
            result = self.result(Path(temporary))
            ControlledGit(result, runner).run(
                ["-C", str(result.source_dir), "status", "--porcelain=v1"]
            )
            host_root = str(result.run_dir)
        argv = runner.calls[0][0]
        self.assertEqual(argv[argv.index("--network") + 1], "none")
        self.assertIn("/executor-run/source", argv)
        self.assertNotIn(host_root, argv[argv.index(PINNED_GIT_BINARY) + 1 :])

    def test_rejects_configuration_network_remote_and_path_escape(self):
        runner = RecordingRunner()
        with tempfile.TemporaryDirectory() as temporary:
            result = self.result(Path(temporary))
            controlled = ControlledGit(result, runner)
            invalid = (
                ["-c", "include.path=/tmp/attacker", "status"],
                ["-cinclude.path=/tmp/attacker", "status"],
                ["--config-env=include.path=ATTACKER", "status"],
                ["--exec-path=/tmp/attacker", "status"],
                ["config", "filter.hostexec.clean", "/tmp/payload"],
                ["--git-dir=/etc", "status"],
                ["fetch", CANONICAL_REPOSITORY_URL],
                ["remote", "add", "origin", CANONICAL_REPOSITORY_URL],
                ["status", "--", "/etc/passwd"],
                ["status", "https://example.invalid/repository.git"],
                ["diff", "--ext-diff"],
            )
            for command in invalid:
                with self.subTest(command=command), self.assertRaises(
                    (InputModelViolation, PathBoundaryError)
                ):
                    controlled.run(command)
        self.assertEqual(runner.calls, [])


class ManifestTests(unittest.TestCase):
    def test_manifest_tracks_content_modes_and_symlink_targets_not_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file_path = root / "file.txt"
            file_path.write_text("value\n")
            link = root / "link"
            link.symlink_to("file.txt")
            entries = build_manifest(root)
        by_path = {entry.path: entry for entry in entries}
        self.assertEqual(by_path["file.txt"].kind, "file")
        self.assertIsNotNone(by_path["file.txt"].sha256)
        self.assertEqual(by_path["link"].kind, "symlink")
        self.assertEqual(by_path["link"].symlink_target, "file.txt")
        self.assertFalse(hasattr(by_path["file.txt"], "mtime"))


@unittest.skipUnless(
    os.environ.get("RUN_PILOT_SOURCE_ACQUISITION") == "1",
    "set RUN_PILOT_SOURCE_ACQUISITION=1 for real Docker acquisition",
)
class RealPinnedAcquisitionIntegrationTests(unittest.TestCase):
    def test_case_001_is_acquired_from_fixed_github_origin(self):
        if shutil.which("docker") is None:
            self.skipTest("Docker is unavailable")
        configured = os.environ.get("PILOT_RUNS_ROOT")
        temporary = None if configured else tempfile.TemporaryDirectory()
        runs_root = (
            Path(configured).resolve() / "source-acquisition"
            if configured
            else Path(temporary.name)
        )
        runs_root.mkdir(parents=True, exist_ok=True)
        try:
            result = ControlledHttpsSourceAcquirer().acquire(
                request(runs_root, run_id="real-case-001")
            )
            evidence = json.loads(result.evidence_path.read_text())
            manifest = json.loads(result.manifest_path.read_text())
            status = ControlledGit(result).run(
                ["-C", str(result.source_dir), "status", "--porcelain=v1"]
            )
        finally:
            if temporary is not None:
                temporary.cleanup()
        self.assertEqual(status.stdout, "")
        self.assertEqual(result.commit, COMMIT)
        self.assertEqual(result.contract_blob, BLOB)
        self.assertEqual(evidence["outcome"], "ACQUIRED_REVIEW_REQUIRED")
        self.assertEqual(
            evidence["origin_anchor"]["canonical_url"],
            CANONICAL_REPOSITORY_URL,
        )
        self.assertTrue(evidence["object_identity"]["fsck_strict"])
        self.assertGreater(len(manifest["entries"]), 0)


if __name__ == "__main__":
    unittest.main()
