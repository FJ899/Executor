import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.action_authorization import AuthorizationContext, packet_payload_sha256
from executor.contracts import load_contract
from executor.gp001_runtime import (
    AuthorizedFileMutation,
    GP001DockerSandboxBackend,
    GP001Runtime,
    build_gp001_sandbox_spec,
)
from executor.sandbox.spec import SandboxExecutionContext, SandboxResult


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_TASK = ROOT / "tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml"
CANONICAL_TEST = ROOT / "test_contracts/GP001_FIX_FAILING_TEST_CASE_001.yaml"
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
            policy_sha256="a" * 64,
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
        base = Path(self.temp.name)
        self.fixture = FixtureRepository(base / "workspace")
        self.contract_root = base / "contract"
        (self.contract_root / "tasks").mkdir(parents=True)
        (self.contract_root / "test_contracts").mkdir()
        test_bytes = CANONICAL_TEST.read_bytes()
        test_path = self.contract_root / "test_contracts/gp001-test.json"
        test_path.write_bytes(test_bytes)

        task = copy.deepcopy(load_contract(CANONICAL_TASK))
        task["repositories"]["target"]["commit"] = self.fixture.commit
        task["test_contract"] = {
            "path": "test_contracts/gp001-test.json",
            "sha256": hashlib.sha256(test_bytes).hexdigest(),
        }
        self.task_path = self.contract_root / "tasks/gp001-task.json"
        self.task_path.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
        self.task = task
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
        spec = build_gp001_sandbox_spec(self.task, "sha256:" + "1" * 64)
        return GP001Runtime(
            task_path=self.task_path,
            runs_root=Path(self.temp.name) / "runs",
            sandbox_backend=backend,
            sandbox_spec=spec,
        )

    def auth(self, runtime, packet_id="packet-1"):
        context = AuthorizationContext(
            run_id="gp001-test-run",
            task_id=self.task["id"],
            risk_class=self.task["risk_class"],
            mode=self.task["mode"],
            executor_commit="a" * 40,
            policy_sha256="b" * 64,
            project_contract_sha256="c" * 64,
            task_contract_sha256=runtime.task_sha256,
            test_contract_sha256=runtime.test_sha256,
            repository_commits={runtime.repository: runtime.input_commit},
            allowed_paths=runtime.allowed,
            external_projects=False,
            auto_merge=False,
            default_network=False,
            default_secrets=(),
            verified_issuer_evidence={"user-proof": ("USER", "test-user")},
        )
        packet = {
            "schema_version": "executor-action-authorization/1.0",
            "packet_id": packet_id,
            "run_id": context.run_id,
            "issued_at": "2026-08-09T06:00:00Z",
            "expires_at": "2026-08-09T07:00:00Z",
            "issuer": {"role": "USER", "id": "test-user", "evidence_ref": "user-proof"},
            "bindings": {
                "task_id": context.task_id,
                "risk_class": context.risk_class,
                "mode": context.mode,
                "executor_commit": context.executor_commit,
                "policy_sha256": context.policy_sha256,
                "project_contract_sha256": context.project_contract_sha256,
                "task_contract_sha256": context.task_contract_sha256,
                "test_contract_sha256": context.test_contract_sha256,
                "repository_commits": context.repository_commits,
            },
            "action": {
                "kind": "WRITE_REPOSITORY",
                "argv": self.mutation.authorization_argv(),
                "paths": [self.mutation.canonical_path()],
                "network": False,
                "secrets": [],
                "external_project": False,
            },
            "decision": {"status": "AUTHORIZED", "reasons": ["GP001 fixture mutation"]},
            "constraints": {
                "max_uses": 1,
                "max_duration_seconds": 3600,
                "manual_confirmation_required": False,
            },
            "integrity": {"algorithm": "SHA-256", "payload_sha256": ""},
        }
        packet["integrity"]["payload_sha256"] = packet_payload_sha256(packet)
        return context, packet

    def test_happy_path_executes_one_authorized_mutation_and_reports_review_required(self):
        backend = SequenceBackend([1, 0, 0, 0])
        runtime = self.runtime(backend)
        context, packet = self.auth(runtime)

        report = runtime.execute(
            workspace=self.fixture.root,
            authorization_packet=packet,
            authorization_context=context,
            mutation=self.mutation,
            now=NOW,
        )

        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertNotEqual(report["status"], "PASS")
        self.assertTrue(report["human_decision_required"])
        self.assertEqual(report["changed_paths"], ["project_registry/registry.py"])
        self.assertEqual(len(report["commands"]), 4)
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_text(),
            self.after_text,
        )
        self.assertTrue((Path(self.temp.name) / "runs/gp001-test-run/report.json").is_file())
        self.assertTrue(Path(report["diff_path"]).is_file())
        self.assertEqual(report["authorization_consumption"], "RUN_LOCAL_REPLAY_GUARD_ONLY")

    def test_green_precondition_blocks_before_authorization_or_mutation(self):
        backend = SequenceBackend([0])
        runtime = self.runtime(backend)
        context, packet = self.auth(runtime)

        report = runtime.execute(
            workspace=self.fixture.root,
            authorization_packet=packet,
            authorization_context=context,
            mutation=self.mutation,
            now=NOW,
        )

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("does not fail", report["error"])
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_bytes(),
            self.before,
        )

    def test_aap_cannot_authorize_a_protected_or_out_of_scope_path(self):
        backend = SequenceBackend([1])
        runtime = self.runtime(backend)
        context, packet = self.auth(runtime)
        packet["action"]["paths"] = ["tests/test_registry.py"]
        packet["integrity"]["payload_sha256"] = packet_payload_sha256(packet)

        report = runtime.execute(
            workspace=self.fixture.root,
            authorization_packet=packet,
            authorization_context=context,
            mutation=self.mutation,
            now=NOW,
        )

        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_bytes(),
            self.before,
        )

    def test_authorization_binds_mutation_payload_hash(self):
        backend = SequenceBackend([1])
        runtime = self.runtime(backend)
        context, packet = self.auth(runtime)
        mutation = AuthorizedFileMutation(
            path=self.mutation.path,
            expected_before_sha256=self.mutation.expected_before_sha256,
            replacement_text="VALUE = 999\n",
            expected_after_sha256=self.mutation.expected_after_sha256,
        )

        report = runtime.execute(
            workspace=self.fixture.root,
            authorization_packet=packet,
            authorization_context=context,
            mutation=mutation,
            now=NOW,
        )

        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("after hash", report["error"])
        self.assertEqual(
            (self.fixture.root / "project_registry/registry.py").read_bytes(),
            self.before,
        )

    def test_regression_failure_never_claims_success(self):
        backend = SequenceBackend([1, 0, 1])
        runtime = self.runtime(backend)
        context, packet = self.auth(runtime)

        report = runtime.execute(
            workspace=self.fixture.root,
            authorization_packet=packet,
            authorization_context=context,
            mutation=self.mutation,
            now=NOW,
        )

        self.assertEqual(report["status"], "FAILED")
        self.assertNotEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertIn("regression command 1", report["error"])

    def test_same_packet_is_rejected_by_run_local_replay_guard(self):
        runtime = self.runtime(SequenceBackend([1]))
        context, packet = self.auth(runtime)
        first = runtime._authorize(packet, context, self.mutation, NOW)
        self.assertEqual(first["packet_id"], "packet-1")
        with self.assertRaisesRegex(Exception, "AUTHORIZATION_REPLAY"):
            runtime._authorize(packet, context, self.mutation, NOW)


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
        backend.protected = ("tests/**", "cases/**", "PILOT_CONTRACT.md", ".github/**", "pyproject.toml")
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
