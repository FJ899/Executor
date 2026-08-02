import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.pilot_case_002 import (
    CASE_002_CONTRACT,
    _BROKEN_TRANSITION,
    PilotCase002DockerSandboxBackend,
    case_002_sandbox_spec,
    execute_case_002,
    verify_case_002_output_checkout,
)
from executor.sandbox.spec import SandboxExecutionContext
from tests.test_pilot_case_001 import FakeSandboxBackend, PilotRepository


class PilotCase002Test(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PilotRepository(
            Path(self.temp.name),
            worker_source=_BROKEN_TRANSITION,
        )
        self.fixture.contract = type(self.fixture.contract)(
            task_id="CASE-002",
            repository=self.fixture.contract.repository,
            input_commit=self.fixture.input_commit,
            contract_blob_sha=self.fixture.contract_blob,
            allowed_path="project_registry/registry.py",
            branch_prefix="executor/case-002",
            purpose="PILOT_CASE_002",
        )
        self.spec = case_002_sandbox_spec("sha256:" + "2" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, backend=None):
        return execute_case_002(
            repository_root=self.fixture.source,
            runs_root=self.fixture.runs,
            sandbox_backend=backend or FakeSandboxBackend(),
            sandbox_spec=self.spec,
            contract=self.fixture.contract,
        )

    def test_happy_path_creates_one_reviewable_case_002_commit(self):
        backend = FakeSandboxBackend()
        report = self.execute(backend)

        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertTrue(report["human_decision_required"])
        self.assertTrue(str(report["branch"]).startswith("executor/case-002-"))
        self.assertEqual(
            report["changed_paths"],
            ["project_registry/registry.py"],
        )
        self.assertEqual(len(backend.calls), 2)
        self.assertTrue(Path(report["diff_path"]).is_file())
        source = (
            Path(report["worktree"]) / "project_registry/registry.py"
        ).read_text(encoding="utf-8")
        self.assertIn("CLOSED -> ACTIVE requires a non-empty reopen_reason", source)
        verify_case_002_output_checkout(
            report["worktree"],
            output_commit=report["output_commit"],
            contract=self.fixture.contract,
        )

    def test_source_checkout_remains_on_broken_input(self):
        before = (
            self.fixture.source / "project_registry/registry.py"
        ).read_text(encoding="utf-8")

        report = self.execute()

        after = (
            self.fixture.source / "project_registry/registry.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertEqual(before, after)
        self.assertEqual(before, _BROKEN_TRANSITION)

    def test_worker_refuses_unrecognized_transition_logic(self):
        self.temp.cleanup()
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = PilotRepository(
            Path(self.temp.name),
            worker_source="# no pinned transition defect\n",
        )
        self.fixture.contract = type(self.fixture.contract)(
            task_id="CASE-002",
            repository=self.fixture.contract.repository,
            input_commit=self.fixture.input_commit,
            contract_blob_sha=self.fixture.contract_blob,
            allowed_path="project_registry/registry.py",
            branch_prefix="executor/case-002",
            purpose="PILOT_CASE_002",
        )

        report = self.execute()

        self.assertEqual(report["status"], "EXECUTION_FAILED")
        self.assertIn("not found exactly once", report["error"])

    def test_test_failure_keeps_diff_without_claiming_success(self):
        report = self.execute(FakeSandboxBackend((0, 1)))

        self.assertEqual(report["status"], "TESTS_FAILED")
        self.assertIsNotNone(report["output_commit"])
        self.assertTrue(Path(report["diff_path"]).is_file())
        self.assertTrue(report["human_decision_required"])

    def test_case_002_sandbox_accepts_only_verified_output(self):
        report = self.execute()
        context = SandboxExecutionContext(
            repository=self.fixture.contract.repository,
            commit=report["output_commit"],
            repository_root=Path(report["worktree"]),
            source_dir=Path(report["worktree"]),
            purpose=self.fixture.contract.purpose,
        )
        backend = object.__new__(PilotCase002DockerSandboxBackend)
        backend.contract = self.fixture.contract
        policy = SimpleNamespace(
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
        )
        with patch.object(
            PilotCase002DockerSandboxBackend,
            "_authoritative_policy",
            return_value=policy,
        ):
            authorized = backend.authorize(context)
        self.assertEqual(authorized, Path(report["worktree"]).resolve())

    def test_case_002_sandbox_refuses_case_001_context(self):
        backend = object.__new__(PilotCase002DockerSandboxBackend)
        backend.contract = CASE_002_CONTRACT
        policy = SimpleNamespace(
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
        )
        context = SandboxExecutionContext(
            repository=CASE_002_CONTRACT.repository,
            commit=CASE_002_CONTRACT.input_commit,
            repository_root=self.fixture.source,
            source_dir=self.fixture.source,
            purpose="PILOT_CASE_001",
        )
        with patch.object(
            PilotCase002DockerSandboxBackend,
            "_authoritative_policy",
            return_value=policy,
        ):
            with self.assertRaisesRegex(Exception, "Unsupported pilot purpose"):
                backend.authorize(context)


if __name__ == "__main__":
    unittest.main()
