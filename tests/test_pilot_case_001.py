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
from executor.sandbox.pilot import PilotCase001DockerSandboxBackend
from executor.sandbox.spec import SandboxExecutionContext, SandboxResult


class FakeSandboxBackend:
    def __init__(self, exit_codes=(0, 0)):
        self.exit_codes = list(exit_codes)
        self.calls = []

    def run(self, *, spec, context, output_dir, argv, container_name=None):
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


class PilotRepository:
    def __init__(self, root: Path, *, worker_source: str | None = None):
        self.root = root
        self.source = root / "source"
        self.runs = root / "runs"
        self.source.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Pilot Test")
        self._git("config", "user.email", "pilot@example.invalid")
        self._git(
            "remote",
            "add",
            "origin",
            "https://github.com/litrgratis-pixel/executor-pilot-target.git",
        )
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
            repository="litrgratis-pixel/executor-pilot-target",
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


class PilotCase001Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PilotRepository(Path(self.temp.name))
        self.spec = case_001_sandbox_spec("sha256:" + "1" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, backend=None):
        return execute_case_001(
            repository_root=self.fixture.source,
            runs_root=self.fixture.runs,
            sandbox_backend=backend or FakeSandboxBackend(),
            sandbox_spec=self.spec,
            contract=self.fixture.contract,
        )

    def test_happy_path_creates_one_reviewable_commit_and_report(self):
        backend = FakeSandboxBackend()
        report = self.execute(backend)

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
        verify_case_001_output_checkout(
            report["worktree"],
            output_commit=report["output_commit"],
            contract=self.fixture.contract,
        )

    def test_wrong_head_is_policy_blocked(self):
        (self.fixture.source / "README.md").write_text("later\n", encoding="utf-8")
        self.fixture._git("add", "README.md")
        self.fixture._git("commit", "-q", "-m", "move head")

        report = self.execute()

        self.assertEqual(report["status"], "POLICY_BLOCKED")
        self.assertIn("expected", report["error"])

    def test_dirty_source_is_policy_blocked(self):
        (self.fixture.source / "dirty.txt").write_text("dirty\n", encoding="utf-8")

        report = self.execute()

        self.assertEqual(report["status"], "POLICY_BLOCKED")
        self.assertIn("clean", report["error"])

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

    def test_output_verifier_rejects_an_extra_changed_path(self):
        path = self.fixture.source / "project_registry/registry.py"
        path.write_text(path.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
        (self.fixture.source / "README.md").write_text("forbidden\n", encoding="utf-8")
        self.fixture._git("add", ".")
        self.fixture._git("commit", "-q", "-m", "forbidden output")
        output_commit = self.fixture._git("rev-parse", "HEAD").stdout.strip()

        with self.assertRaisesRegex(Exception, "changed paths"):
            verify_case_001_output_checkout(
                self.fixture.source,
                output_commit=output_commit,
                contract=self.fixture.contract,
            )

    def test_pilot_sandbox_accepts_only_the_verified_output(self):
        report = self.execute()
        context = SandboxExecutionContext(
            repository=self.fixture.contract.repository,
            commit=report["output_commit"],
            repository_root=Path(report["worktree"]),
            source_dir=Path(report["worktree"]),
            purpose=self.fixture.contract.purpose,
        )
        backend = object.__new__(PilotCase001DockerSandboxBackend)
        backend.contract = self.fixture.contract
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
        report = self.execute()
        context = SandboxExecutionContext(
            repository=self.fixture.contract.repository,
            commit=report["output_commit"],
            repository_root=Path(report["worktree"]),
            source_dir=Path(report["worktree"]),
            purpose=self.fixture.contract.purpose,
        )
        backend = object.__new__(PilotCase001DockerSandboxBackend)
        backend.contract = self.fixture.contract
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
