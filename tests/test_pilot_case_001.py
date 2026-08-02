import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.pilot_case_001 import (
    _BROKEN_ADD_MANY,
    PilotCase001Contract,
    case_001_sandbox_spec,
    execute_case_001,
    verify_case_001_output_checkout,
)
from executor.source_acquisition import (
    ALLOWED_REPOSITORY,
    CANONICAL_REPOSITORY_URL,
    INPUT_MODEL,
    PINNED_GIT_BINARY,
    PINNED_GIT_IMAGE,
    PINNED_GIT_PLATFORM,
    PINNED_GIT_VERSION,
    CommandResult,
    SourceAcquisitionRequest,
    SourceAcquisitionResult,
    _validate_controlled_git_args,
    build_manifest,
    sha256_file,
    validate_request,
)
from executor.sandbox.pilot import PilotCase001DockerSandboxBackend
from executor.sandbox.spec import SandboxExecutionContext, SandboxResult


class FakeSandboxBackend:
    def __init__(self, exit_codes=(0, 0)):
        self.exit_codes = list(exit_codes)
        self.calls = []

    def run(self, *, spec, context, output_dir, argv, container_name=None):
        del container_name
        self.calls.append((spec, context, Path(output_dir), list(argv)))
        exit_code = self.exit_codes.pop(0)
        return SandboxResult(
            container_name="fake",
            execution_id=f"{len(self.calls):032x}",
            policy_sha256="a" * 64,
            argv=tuple(argv),
            exit_code=exit_code,
            stdout="ok\n" if exit_code == 0 else "",
            stderr="" if exit_code == 0 else "failed",
            timed_out=False,
            duration_seconds=0.01,
            output_dir=Path(output_dir),
            cleanup_verified=True,
        )


def _safe_git_environment() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/bin/false",
        "SSH_ASKPASS": "/bin/false",
        "GIT_SSH_COMMAND": "/bin/false",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "LC_ALL": "C",
    }


def _host_git(*args: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
        env=_safe_git_environment(),
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr or completed.stdout)
    return completed


class LocalControlledGit:
    """Test-only adapter operating solely below the controlled run directory."""

    def __init__(self, result: SourceAcquisitionResult, **_kwargs):
        self.result = result

    def run(self, git_args):
        _validate_controlled_git_args(git_args, self.result.run_dir)
        completed = subprocess.run(
            ["git", *map(str, git_args)],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
            env=_safe_git_environment(),
        )
        if completed.returncode:
            raise RuntimeError(completed.stderr or completed.stdout)
        return CommandResult(
            argv=tuple(["git", *map(str, git_args)]),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class FixtureSourceAcquirer:
    """Copy fixture object bytes, then use Git only on a new controlled repo."""

    def __init__(self, fixture: "PilotRepository"):
        self.fixture = fixture

    def acquire(self, request: SourceAcquisitionRequest) -> SourceAcquisitionResult:
        request = validate_request(request)
        if request.repository != self.fixture.contract.repository:
            raise AssertionError("fixture repository mismatch")
        if request.commit != self.fixture.contract.input_commit:
            raise AssertionError("fixture commit mismatch")
        if request.contract_blob != self.fixture.contract.contract_blob_sha:
            raise AssertionError("fixture contract blob mismatch")

        request.runs_root.mkdir(parents=True, exist_ok=True)
        run_dir = request.runs_root / request.run_id
        run_dir.mkdir(mode=0o700)
        acquisition = run_dir / "acquisition"
        git_dir = acquisition / "repository.git"
        source_dir = run_dir / "source"
        evidence_dir = run_dir / "evidence"
        acquisition.mkdir()
        evidence_dir.mkdir()
        (run_dir / "isolated-home").mkdir()
        (run_dir / "isolated-xdg").mkdir()

        _host_git("init", "--bare", str(git_dir))
        shutil.copytree(
            self.fixture.source / ".git" / "objects",
            git_dir / "objects",
            dirs_exist_ok=True,
            symlinks=False,
        )
        _host_git(
            "--git-dir",
            str(git_dir),
            "update-ref",
            "refs/executor/input",
            request.commit,
        )
        for key, value in (
            ("core.hooksPath", os.devnull),
            ("core.fsmonitor", "false"),
            ("core.attributesFile", os.devnull),
            ("commit.gpgSign", "false"),
            ("user.name", "Creative OS Executor"),
            ("user.email", "executor@localhost"),
        ):
            _host_git("--git-dir", str(git_dir), "config", key, value)
        _host_git(
            "--git-dir",
            str(git_dir),
            "worktree",
            "add",
            "--detach",
            str(source_dir),
            request.commit,
        )
        root_tree = _host_git(
            "--git-dir", str(git_dir), "rev-parse", f"{request.commit}^{{tree}}"
        ).stdout.strip()
        manifest_path = evidence_dir / "source_manifest.json"
        manifest = {
            "schema": "executor.source-manifest.v1",
            "root": str(source_dir),
            "entries": [entry.__dict__ for entry in build_manifest(source_dir)],
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        evidence_path = evidence_dir / "source_acquisition.json"
        evidence = {
            "schema": "executor.source-acquisition-evidence.v1",
            "input_model": INPUT_MODEL,
            "request": {
                "run_id": request.run_id,
                "repository": request.repository,
                "commit": request.commit,
                "contract_blob": request.contract_blob,
                "contract_path": request.contract_path,
            },
            "origin_anchor": {
                "canonical_url": CANONICAL_REPOSITORY_URL,
                "local_checkout_used": False,
                "user_supplied_url_used": False,
            },
            "toolchain": {
                "image": PINNED_GIT_IMAGE,
                "platform": PINNED_GIT_PLATFORM,
                "binary": PINNED_GIT_BINARY,
                "observed_version": PINNED_GIT_VERSION,
            },
            "object_identity": {
                "commit": request.commit,
                "root_tree": root_tree,
                "contract_blob": request.contract_blob,
                "fsck_strict": True,
            },
            "manifest": {
                "path": str(manifest_path),
                "entry_count": len(manifest["entries"]),
                "sha256": sha256_file(manifest_path),
            },
            "commands": [],
            "outcome": "ACQUIRED_REVIEW_REQUIRED",
            "error": None,
        }
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return SourceAcquisitionResult(
            input_model=INPUT_MODEL,
            repository=request.repository,
            canonical_url=CANONICAL_REPOSITORY_URL,
            commit=request.commit,
            root_tree=root_tree,
            contract_path=request.contract_path,
            contract_blob=request.contract_blob,
            run_dir=run_dir,
            git_dir=git_dir,
            source_dir=source_dir,
            manifest_path=manifest_path,
            evidence_path=evidence_path,
            toolchain_image=PINNED_GIT_IMAGE,
            toolchain_platform=PINNED_GIT_PLATFORM,
            git_binary=PINNED_GIT_BINARY,
            git_version=PINNED_GIT_VERSION,
        )


class PilotRepository:
    def __init__(self, root: Path, *, worker_source: str | None = None):
        self.root = root
        self.source = root / "source"
        self.runs = root / "runs"
        self.source.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Pilot Test")
        self._git("config", "user.email", "pilot@example.invalid")
        self._git("remote", "add", "origin", CANONICAL_REPOSITORY_URL)
        (self.source / "project_registry").mkdir()
        (self.source / "tests").mkdir()
        (self.source / "PILOT_CONTRACT.md").write_text(
            "pinned pilot contract\n", encoding="utf-8"
        )
        (self.source / "project_registry/registry.py").write_text(
            worker_source if worker_source is not None else _BROKEN_ADD_MANY,
            encoding="utf-8",
        )
        (self.source / "tests/test_placeholder.py").write_text(
            "import unittest\n\nclass Placeholder(unittest.TestCase):\n"
            "    def test_ok(self):\n        self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self._git("add", ".")
        self._git("commit", "-q", "-m", "broken input")
        self.input_commit = self._git("rev-parse", "HEAD").stdout.strip()
        self.contract_blob = self._git(
            "rev-parse", f"{self.input_commit}:PILOT_CONTRACT.md"
        ).stdout.strip()
        self.contract = PilotCase001Contract(
            task_id="CASE-001",
            repository=ALLOWED_REPOSITORY,
            input_commit=self.input_commit,
            contract_blob_sha=self.contract_blob,
            allowed_path="project_registry/registry.py",
        )

    def _git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.source), *args],
            check=True,
            capture_output=True,
            text=True,
        )

    @contextlib.contextmanager
    def controlled_runtime(self):
        with (
            patch(
                "executor.pilot_core.ControlledHttpsSourceAcquirer",
                return_value=FixtureSourceAcquirer(self),
            ),
            patch("executor.pilot_core.ControlledGit", LocalControlledGit),
        ):
            yield


class PilotCase001Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PilotRepository(Path(self.temp.name))
        self.spec = case_001_sandbox_spec("sha256:" + "1" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, backend=None, *, repository_root=None):
        with self.fixture.controlled_runtime():
            return execute_case_001(
                repository_root=repository_root,
                runs_root=self.fixture.runs,
                sandbox_backend=backend or FakeSandboxBackend(),
                sandbox_spec=self.spec,
                contract=self.fixture.contract,
            )

    def test_happy_path_creates_one_reviewable_commit_and_report(self):
        backend = FakeSandboxBackend()
        with self.fixture.controlled_runtime():
            report = execute_case_001(
                repository_root=None,
                runs_root=self.fixture.runs,
                sandbox_backend=backend,
                sandbox_spec=self.spec,
                contract=self.fixture.contract,
            )
            verify_case_001_output_checkout(
                report["worktree"],
                output_commit=report["output_commit"],
                contract=self.fixture.contract,
            )

        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertTrue(report["human_decision_required"])
        self.assertEqual(
            report["changed_paths"], ["project_registry/registry.py"]
        )
        self.assertEqual(len(backend.calls), 2)
        self.assertTrue(Path(report["diff_path"]).is_file())
        self.assertTrue(
            (self.fixture.runs / report["run_id"] / "report.json").is_file()
        )
        self.assertEqual(
            report["source_acquisition"]["input_model"],
            "CONTROLLED_HTTPS_FETCH_V1",
        )

    def test_local_checkout_argument_is_blocked_without_writing_into_it(self):
        runs_root = self.fixture.source / "runs"
        report = execute_case_001(
            repository_root=self.fixture.source,
            runs_root=runs_root,
            sandbox_backend=FakeSandboxBackend(),
            sandbox_spec=self.spec,
            contract=self.fixture.contract,
        )
        self.assertEqual(report["status"], "POLICY_BLOCKED")
        self.assertIn("local repository_root", report["error"])
        self.assertFalse(runs_root.exists())

    def test_dirty_or_moved_local_checkout_is_not_used(self):
        (self.fixture.source / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        (self.fixture.source / "README.md").write_text("later\n", encoding="utf-8")
        self.fixture._git("add", "README.md")
        self.fixture._git("commit", "-q", "-m", "move head")
        report = self.execute()
        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertTrue((self.fixture.source / "dirty.txt").exists())

    def test_test_failure_keeps_diff_but_does_not_claim_success(self):
        report = self.execute(FakeSandboxBackend((0, 1)))
        self.assertEqual(report["status"], "TESTS_FAILED")
        self.assertIsNotNone(report["output_commit"])
        self.assertTrue(Path(report["diff_path"]).is_file())
        self.assertTrue(report["human_decision_required"])

    def test_worker_refuses_an_unrecognized_input(self):
        self.temp.cleanup()
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PilotRepository(
            Path(self.temp.name), worker_source="# no pinned defect\n"
        )
        report = self.execute()
        self.assertEqual(report["status"], "EXECUTION_FAILED")
        self.assertIn("not found exactly once", report["error"])

    def test_output_verifier_rejects_a_second_commit(self):
        with self.fixture.controlled_runtime():
            report = execute_case_001(
                repository_root=None,
                runs_root=self.fixture.runs,
                sandbox_backend=FakeSandboxBackend(),
                sandbox_spec=self.spec,
                contract=self.fixture.contract,
            )
            from executor.source_acquisition import load_source_acquisition_result

            git = LocalControlledGit(
                load_source_acquisition_result(Path(report["worktree"]).parent)
            )
            extra = Path(report["worktree"]) / "README.md"
            extra.write_text("forbidden\n", encoding="utf-8")
            git.run(["-C", report["worktree"], "add", "README.md"])
            git.run(["-C", report["worktree"], "commit", "-m", "forbidden output"])
            second = git.run(
                ["-C", report["worktree"], "rev-parse", "HEAD"]
            ).stdout.strip()
            with self.assertRaisesRegex(Exception, "one commit directly|changed paths"):
                verify_case_001_output_checkout(
                    report["worktree"],
                    output_commit=second,
                    contract=self.fixture.contract,
                )

    def test_pilot_sandbox_accepts_only_the_verified_output(self):
        with self.fixture.controlled_runtime():
            report = execute_case_001(
                repository_root=None,
                runs_root=self.fixture.runs,
                sandbox_backend=FakeSandboxBackend(),
                sandbox_spec=self.spec,
                contract=self.fixture.contract,
            )
            context = SandboxExecutionContext(
                repository=self.fixture.contract.repository,
                commit=report["output_commit"],
                repository_root=Path(report["worktree"]),
                source_dir=Path(report["worktree"]),
                purpose=self.fixture.contract.purpose,
            )
            backend = object.__new__(PilotCase001DockerSandboxBackend)
            backend.contract = self.fixture.contract
            backend.docker_binary = "docker"
            policy = SimpleNamespace(
                external_projects=False,
                auto_merge=False,
                default_network=False,
                default_secrets=(),
            )
            with patch.object(
                PilotCase001DockerSandboxBackend,
                "_authoritative_policy",
                return_value=policy,
            ):
                authorized = backend.authorize(context)
        self.assertEqual(authorized, Path(report["worktree"]).resolve())

    def test_pilot_sandbox_refuses_global_external_execution(self):
        with self.fixture.controlled_runtime():
            report = execute_case_001(
                repository_root=None,
                runs_root=self.fixture.runs,
                sandbox_backend=FakeSandboxBackend(),
                sandbox_spec=self.spec,
                contract=self.fixture.contract,
            )
            context = SandboxExecutionContext(
                repository=self.fixture.contract.repository,
                commit=report["output_commit"],
                repository_root=Path(report["worktree"]),
                source_dir=Path(report["worktree"]),
                purpose=self.fixture.contract.purpose,
            )
            backend = object.__new__(PilotCase001DockerSandboxBackend)
            backend.contract = self.fixture.contract
            backend.docker_binary = "docker"
            policy = SimpleNamespace(
                external_projects=True,
                auto_merge=False,
                default_network=False,
                default_secrets=(),
            )
            with patch.object(
                PilotCase001DockerSandboxBackend,
                "_authoritative_policy",
                return_value=policy,
            ):
                with self.assertRaisesRegex(Exception, "global external"):
                    backend.authorize(context)


if __name__ == "__main__":
    unittest.main()
