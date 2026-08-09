import copy
import hashlib
import inspect
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.contracts import load_contract
from executor.gp001_runtime import (
    AuthorizedFileMutation,
    GP001Blocked,
    GP001DockerSandboxBackend,
    GP001Runtime,
    build_gp001_sandbox_spec,
)
from executor.repository_access import canonical_repository_path, validate_scope_pattern
from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError
from executor.sandbox.spec import SandboxExecutionContext, SandboxResult


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TASK = ROOT / "tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml"
NOW = datetime(2026, 8, 9, 6, 30, tzinfo=timezone.utc)


class SequenceBackend:
    def __init__(self, exit_codes):
        self.exit_codes = list(exit_codes)
        self.calls = []

    def run(self, *, spec, context, output_dir, argv, container_name=None):
        del spec, container_name
        self.calls.append((context, Path(output_dir), list(argv)))
        exit_code = self.exit_codes.pop(0)
        return SandboxResult(
            container_name="fake",
            execution_id=f"{len(self.calls):032x}",
            policy_sha256="b" * 64,
            argv=tuple(argv),
            exit_code=exit_code,
            stdout="ok\n" if exit_code == 0 else "",
            stderr="" if exit_code == 0 else "expected failure\n",
            timed_out=False,
            duration_seconds=0.01,
            output_dir=Path(output_dir),
            cleanup_verified=True,
        )


class FixtureRepository:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "GP001 Test")
        self.git("config", "user.email", "gp001@example.invalid")
        self.git(
            "remote",
            "add",
            "origin",
            "https://github.com/litrgratis-pixel/executor-pilot-target.git",
        )
        (root / "project_registry").mkdir()
        (root / "tests").mkdir()
        (root / "cases").mkdir()
        (root / ".github/workflows").mkdir(parents=True)
        (root / "project_registry/registry.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "tests/test_registry.py").write_text("# protected\n", encoding="utf-8")
        (root / "cases/README.md").write_text("protected\n", encoding="utf-8")
        (root / "PILOT_CONTRACT.md").write_text("protected\n", encoding="utf-8")
        (root / ".github/workflows/ci.yml").write_text("name: protected\n", encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "pinned input")
        self.commit = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args],
            text=True,
            capture_output=True,
            check=True,
        )


class GP001RuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FixtureRepository(Path(self.temp.name) / "workspace")
        self.task = copy.deepcopy(load_contract(CANONICAL_TASK))
        self.task["repositories"]["target"]["commit"] = self.fixture.commit
        self.before = (self.fixture.root / "project_registry/registry.py").read_bytes()
        self.after_text = "VALUE = 2\n"
        self.mutation = AuthorizedFileMutation(
            path="project_registry/registry.py",
            expected_before_sha256=hashlib.sha256(self.before).hexdigest(),
            replacement_text=self.after_text,
            expected_after_sha256=hashlib.sha256(self.after_text.encode()).hexdigest(),
        )

    def tearDown(self):
        self.temp.cleanup()

    def runtime(self, backend):
        runtime = object.__new__(GP001Runtime)
        runtime.policy_snapshot = SimpleNamespace(
            commit="a" * 40,
            source_sha256="b" * 64,
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
        )
        runtime.task_path = CANONICAL_TASK
        runtime.task = self.task
        runtime.task_sha256 = hashlib.sha256(CANONICAL_TASK.read_bytes()).hexdigest()
        runtime.test_sha256 = self.task["test_contract"]["sha256"]
        runtime.project_contract_sha256 = "c" * 64
        runtime.repository = self.task["repositories"]["target"]["name"]
        runtime.input_commit = self.fixture.commit
        runtime.allowed = tuple(
            canonical_repository_path(p)
            for p in self.task["golden_path"]["scope"]["allowed_paths"]
        )
        runtime.protected = tuple(
            validate_scope_pattern(p)
            for p in self.task["golden_path"]["scope"]["protected_paths"]
        )
        commands = self.task["golden_path"]["commands"]
        runtime.target_command = list(commands["target_test_argv"])
        runtime.regression_commands = [list(v) for v in commands["regression_argv"]]
        runtime.runs_root = Path(self.temp.name) / "runs"
        runtime.backend = backend
        runtime.spec = build_gp001_sandbox_spec(self.task, "sha256:" + "1" * 64)
        runtime._consumed_packet_ids = set()
        return runtime

    def execute(self, runtime, mutation=None, run_id="gp001-test-run"):
        return runtime.execute(
            workspace=self.fixture.root,
            mutation=mutation or self.mutation,
            run_id=run_id,
            now=NOW,
        )

    def test_happy_path_executes_one_policy_authorized_mutation_and_reports_review_required(self):
        backend = SequenceBackend([1, 0, 0, 0])
        runtime = self.runtime(backend)

        report = self.execute(runtime)

        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertNotEqual(report["status"], "PASS")
        self.assertTrue(report["human_decision_required"])
        self.assertEqual(report["changed_paths"], ["project_registry/registry.py"])
        self.assertEqual(len(report["commands"]), 4)
        self.assertEqual(report["authorization"]["issuer_role"], "POLICY_VERIFIER")
        self.assertEqual(
            report["authorization_model"],
            "CANONICAL_USER_APPROVED_TASK_PLUS_POLICY_VERIFIER_ACTION_GATE",
        )
        self.assertEqual(
            report["authorization"]["action_argv"],
            self.mutation.authorization_argv(),
        )
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_text(),
            self.after_text,
        )
        self.assertTrue((Path(self.temp.name) / "runs/gp001-test-run/report.json").is_file())
        self.assertTrue(Path(report["diff_path"]).is_file())
        self.assertEqual(report["authorization_consumption"], "RUN_LOCAL_REPLAY_GUARD_ONLY")

    def test_green_precondition_blocks_before_authorization_or_mutation(self):
        runtime = self.runtime(SequenceBackend([0]))

        report = self.execute(runtime)

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("does not fail", report["error"])
        self.assertIsNone(report["authorization"])
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_bytes(),
            self.before,
        )

    def test_protected_or_out_of_scope_mutation_is_blocked(self):
        runtime = self.runtime(SequenceBackend([1]))
        before = (self.fixture.root / "tests/test_registry.py").read_bytes()
        after = b"# changed acceptance\n"
        mutation = AuthorizedFileMutation(
            path="tests/test_registry.py",
            expected_before_sha256=hashlib.sha256(before).hexdigest(),
            replacement_text=after.decode(),
            expected_after_sha256=hashlib.sha256(after).hexdigest(),
        )

        report = self.execute(runtime, mutation=mutation)

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("outside the frozen GP001 contract", report["error"])
        self.assertEqual((self.fixture.root / "tests/test_registry.py").read_bytes(), before)
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_bytes(),
            self.before,
        )

    def test_authorization_binds_mutation_payload_hash(self):
        runtime = self.runtime(SequenceBackend([1]))
        mutation = AuthorizedFileMutation(
            path=self.mutation.path,
            expected_before_sha256=self.mutation.expected_before_sha256,
            replacement_text="VALUE = 999\n",
            expected_after_sha256=self.mutation.expected_after_sha256,
        )

        report = self.execute(runtime, mutation=mutation)

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("after hash", report["error"])
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_bytes(),
            self.before,
        )

    def test_regression_failure_never_claims_success(self):
        runtime = self.runtime(SequenceBackend([1, 0, 1]))

        report = self.execute(runtime)

        self.assertEqual(report["status"], "FAILED")
        self.assertNotEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertIn("regression command 1", report["error"])

    def test_same_policy_packet_identity_is_rejected_by_run_local_replay_guard(self):
        runtime = self.runtime(SequenceBackend([]))
        first = runtime._authorize(run_id="same-run", mutation=self.mutation, now=NOW)
        self.assertEqual(first["issuer_role"], "POLICY_VERIFIER")
        with self.assertRaisesRegex(GP001Blocked, "AUTHORIZATION_REPLAY"):
            runtime._authorize(run_id="same-run", mutation=self.mutation, now=NOW)

    def test_public_runtime_interface_does_not_accept_caller_supplied_aap_context_or_backend(self):
        execute_parameters = inspect.signature(GP001Runtime.execute).parameters
        init_parameters = inspect.signature(GP001Runtime.__init__).parameters
        self.assertNotIn("authorization_packet", execute_parameters)
        self.assertNotIn("authorization_context", execute_parameters)
        self.assertNotIn("sandbox_backend", init_parameters)
        self.assertNotIn("task_path", init_parameters)

    def test_public_constructor_rejects_non_authoritative_executor_root(self):
        empty = Path(self.temp.name) / "not-executor"
        empty.mkdir()
        with self.assertRaisesRegex(GP001Blocked, "authoritative GP001 runtime inputs"):
            GP001Runtime(
                executor_root=empty,
                executor_commit="a" * 40,
                runs_root=Path(self.temp.name) / "runs-public",
                image="sha256:" + "1" * 64,
            )


class GP001SandboxBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = FixtureRepository(Path(self.temp.name) / "workspace")
        task = copy.deepcopy(load_contract(CANONICAL_TASK))
        task["repositories"]["target"]["commit"] = self.fixture.commit
        backend = object.__new__(GP001DockerSandboxBackend)
        backend.repository = task["repositories"]["target"]["name"]
        backend.input_commit = self.fixture.commit
        backend.allowed = ("project_registry/registry.py",)
        backend.protected = (
            "tests/**",
            "cases/**",
            "PILOT_CONTRACT.md",
            ".github/**",
            "pyproject.toml",
        )
        backend.docker_binary = "docker"
        backend.policy_snapshot = SimpleNamespace(source_sha256="a" * 64)
        self.backend = backend

    def tearDown(self):
        self.temp.cleanup()

    def policy(self):
        return SimpleNamespace(
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
        )

    def context(self, purpose):
        return SandboxExecutionContext(
            repository="litrgratis-pixel/executor-pilot-target",
            commit=self.fixture.commit,
            repository_root=self.fixture.root,
            source_dir=self.fixture.root,
            purpose=purpose,
        )

    def test_backend_constructor_rejects_any_noncanonical_fixture_identity(self):
        cases = (
            ("name", "litrgratis-pixel/not-the-controlled-fixture"),
            ("commit", "1" * 40),
        )
        for key, value in cases:
            with self.subTest(key=key):
                task = copy.deepcopy(load_contract(CANONICAL_TASK))
                task["repositories"]["target"][key] = value
                with patch.object(DockerSandboxBackend, "__init__", return_value=None):
                    with self.assertRaisesRegex(SandboxExecutionError, "canonical controlled"):
                        GP001DockerSandboxBackend(
                            policy_snapshot=SimpleNamespace(),
                            task=task,
                        )

    def test_clean_prechange_and_exact_one_file_postchange_are_allowed(self):
        with patch.object(GP001DockerSandboxBackend, "_authoritative_policy", return_value=self.policy()):
            self.assertEqual(
                self.backend.authorize(self.context("GP001_PRECHANGE")),
                self.fixture.root.resolve(),
            )
            (self.fixture.root / "project_registry/registry.py").write_text("VALUE = 2\n")
            self.assertEqual(
                self.backend.authorize(self.context("GP001_POSTCHANGE")),
                self.fixture.root.resolve(),
            )

    def test_postchange_rejects_any_extra_path(self):
        (self.fixture.root / "project_registry/registry.py").write_text("VALUE = 2\n")
        (self.fixture.root / "extra.txt").write_text("not authorized\n")
        with patch.object(GP001DockerSandboxBackend, "_authoritative_policy", return_value=self.policy()):
            with self.assertRaisesRegex(Exception, "scope mismatch"):
                self.backend.authorize(self.context("GP001_POSTCHANGE"))


if __name__ == "__main__":
    unittest.main()
