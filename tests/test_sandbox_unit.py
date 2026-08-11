import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.sandbox.command_policy import CommandDenied, validate_argv
from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError, SandboxUnavailable
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot
from executor.sandbox.spec import CommandRule, SandboxExecutionContext, SandboxSpec

ROOT = Path(__file__).resolve().parents[1]
IMAGE_ID = "sha256:" + "1" * 64
EXECUTION_ID = "a" * 32
CURRENT_EXECUTOR_REPOSITORY = "JTJ07/Executor"


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


class SandboxUnitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.commit = run_git(ROOT, "rev-parse", "HEAD")
        cls.snapshot = load_execution_policy_snapshot(ROOT, commit=cls.commit)

    def backend(self):
        return DockerSandboxBackend(policy_snapshot=self.snapshot)

    def spec(self, **changes):
        values = dict(
            image=IMAGE_ID,
            command_rules=(CommandRule("python", ("/source/sandbox_fixture.py",)),),
            max_cpu=1.0,
            max_memory_mb=64,
            max_disk_mb=8,
            timeout_seconds=2,
            pids_limit=16,
            labels={"creative-os-executor-test": "true"},
        )
        values.update(changes)
        return SandboxSpec(**values)

    def context(self, root=ROOT, source=None, *, repository=CURRENT_EXECUTOR_REPOSITORY, purpose="EXECUTOR_FIXTURE", commit=None):
        return SandboxExecutionContext(
            repository=repository,
            commit=commit or self.commit,
            repository_root=Path(root),
            source_dir=Path(source or ROOT / "tests/fixtures/sandbox"),
            purpose=purpose,
        )

    def completed(self, args, returncode=0, stdout="", stderr=""):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    def test_backend_requires_verified_policy_snapshot(self):
        with self.assertRaisesRegex(SandboxExecutionError, "raw policy"):
            DockerSandboxBackend(policy_snapshot={"execution": {}})

    def test_structured_command_allowed(self):
        validate_argv(["python", "/source/sandbox_fixture.py", "read_source"], self.spec().command_rules)

    def test_python_c_is_denied(self):
        with self.assertRaises(CommandDenied):
            validate_argv(["python", "-c", "print(1)"], self.spec().command_rules)

    def test_empty_command_denied(self):
        with self.assertRaises(CommandDenied):
            validate_argv([], self.spec().command_rules)

    def test_create_command_contains_isolation_and_ownership(self):
        backend = self.backend()
        with patch.object(backend, "authorize", return_value=ROOT / "tests/fixtures/sandbox"):
            command = backend.build_create_command(
                spec=self.spec(),
                context=self.context(),
                container_name="test-container",
                argv=["python", "/source/sandbox_fixture.py", "read_source"],
                execution_id=EXECUTION_ID,
            )
        joined = " ".join(command)
        for marker in (
            "--network none", "--read-only", "--cap-drop ALL", "no-new-privileges",
            "--pids-limit 16", "--memory 64m", "--user 65534:65534",
            "HOME=/nonexistent", "readonly",
            f"creative-os-executor.execution-id={EXECUTION_ID}",
            f"creative-os-executor.policy-sha256={self.snapshot.source_sha256}",
        ):
            self.assertIn(marker, joined)
        self.assertNotIn("docker.sock", joined)

    def test_mutable_image_and_forged_ownership_label_are_rejected(self):
        backend = self.backend()
        cases = (
            self.spec(image="python:3.11"),
            self.spec(labels={"creative-os-executor.execution-id": "forged"}),
        )
        for spec in cases:
            with self.subTest(spec=spec), patch.object(backend, "authorize", return_value=ROOT):
                with self.assertRaises(SandboxExecutionError):
                    backend.build_create_command(
                        spec=spec,
                        context=self.context(),
                        container_name="x",
                        argv=["python", "/source/sandbox_fixture.py"],
                        execution_id=EXECUTION_ID,
                    )

    def test_external_project_is_rejected_before_repository_or_docker_calls(self):
        backend = self.backend()
        context = self.context(repository="other/Project", purpose="PROJECT")
        with patch("executor.sandbox.docker.verify_repository_checkout") as verify, patch.object(backend, "preflight") as preflight:
            with self.assertRaisesRegex(SandboxExecutionError, "External project execution is disabled"):
                backend.run(
                    spec=self.spec(), context=context, output_dir=ROOT / "artifacts-test",
                    argv=["python", "/source/sandbox_fixture.py", "read_source"],
                )
            verify.assert_not_called()
            preflight.assert_not_called()

    def test_external_project_can_be_authorized_only_when_policy_allows(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            context = self.context(root, source, repository="other/Project", purpose="PROJECT", commit="b" * 40)
            with patch.object(backend, "_authoritative_policy", return_value=SimpleNamespace(external_projects=True)), patch(
                "executor.sandbox.docker.verify_repository_checkout", return_value=root
            ), patch("executor.sandbox.docker.verify_source_tree", return_value=("source/file",)):
                self.assertEqual(backend.authorize(context), source.resolve())

    def test_fixture_purpose_is_restricted_to_executor_repository(self):
        backend = self.backend()
        context = self.context(repository="other/Project", purpose="EXECUTOR_FIXTURE")
        with self.assertRaisesRegex(SandboxExecutionError, "restricted to the Executor"):
            backend.authorize(context)

    def test_fixture_root_and_commit_must_match_policy_snapshot(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(root=temp, source=temp)
            with self.assertRaisesRegex(SandboxExecutionError, "must match the bound policy snapshot"):
                backend.authorize(context)

    def test_source_directory_must_stay_inside_verified_repository(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            context = self.context(root, outside, repository="other/Project", purpose="PROJECT", commit="b" * 40)
            with patch.object(backend, "_authoritative_policy", return_value=SimpleNamespace(external_projects=True)), patch(
                "executor.sandbox.docker.verify_repository_checkout", return_value=root.resolve()
            ):
                with self.assertRaisesRegex(SandboxExecutionError, "escapes the verified repository"):
                    backend.authorize(context)

    def test_network_secret_and_home_capabilities_are_rejected(self):
        backend = self.backend()
        cases = (
            SandboxSpec(image=IMAGE_ID, command_rules=(CommandRule("python"),), network=True),
            SandboxSpec(image=IMAGE_ID, command_rules=(CommandRule("python"),), secrets=("TOKEN",)),
            SandboxSpec(image=IMAGE_ID, command_rules=(CommandRule("python"),), home_access=True),
        )
        for spec in cases:
            with self.subTest(spec=spec), patch.object(backend, "authorize", return_value=ROOT):
                with self.assertRaises(SandboxExecutionError):
                    backend.build_create_command(
                        spec=spec, context=self.context(), container_name="x",
                        argv=["python"], execution_id=EXECUTION_ID,
                    )

    def test_no_host_fallback_without_docker(self):
        with patch("executor.sandbox.docker.shutil.which", return_value=None):
            with self.assertRaises(SandboxUnavailable):
                self.backend().preflight()

    def test_container_name_collision_is_blocked(self):
        backend = self.backend()
        with patch.object(backend, "_list_exact", return_value=(True, {"occupied"}, "")):
            with self.assertRaisesRegex(SandboxExecutionError, "already exists"):
                backend._ensure_name_available("occupied")

    def test_cleanup_requires_owned_container_and_successful_absence_query(self):
        backend = self.backend()
        cases = (
            ([self.completed(["inspect"], 1, stderr="daemon unavailable"), self.completed(["ps"], 1, stderr="daemon unavailable")], False),
            ([self.completed(["inspect"], 1, stderr="no object"), self.completed(["ps"], 0, stdout="")], True),
            ([self.completed(["inspect"], 0, stdout="foreign")], False),
            ([self.completed(["inspect"], 0, stdout=EXECUTION_ID), self.completed(["rm"], 0), self.completed(["ps"], 0, stdout="")], True),
        )
        for responses, expected in cases:
            with self.subTest(expected=expected), patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
                verified, _ = backend._cleanup("x", EXECUTION_ID)
                self.assertEqual(verified, expected)

    def test_foreign_owner_container_is_not_removed(self):
        backend = self.backend()
        with patch("executor.sandbox.docker.subprocess.run", return_value=self.completed(["inspect"], 0, stdout="foreign")) as run:
            verified, detail = backend._cleanup("x", EXECUTION_ID)
        self.assertFalse(verified)
        self.assertIn("ownership mismatch", detail)
        self.assertEqual(run.call_count, 1)

    def test_cleanup_failure_cannot_report_run_success(self):
        backend = self.backend()
        responses = [
            self.completed(["ps"], 0, stdout=""), self.completed(["create"], 0),
            self.completed(["start"], 0, stdout="ok"),
            self.completed(["inspect"], 1, stderr="daemon unavailable"),
            self.completed(["ps"], 1, stderr="daemon unavailable"),
        ]
        with patch.object(backend, "authorize", return_value=ROOT / "tests/fixtures/sandbox"), patch.object(
            backend, "preflight"
        ), patch.object(backend, "build_create_command", return_value=["docker", "create"]), patch(
            "executor.sandbox.docker.subprocess.run", side_effect=responses
        ):
            result = backend.run(
                spec=self.spec(), context=self.context(), output_dir=ROOT / "artifacts-test",
                argv=["python", "/source/sandbox_fixture.py", "read_source"], container_name="x",
            )
        self.assertFalse(result.cleanup_verified)
        self.assertFalse(result.ok)
        self.assertIn("CLEANUP_UNVERIFIED", result.stderr)
        self.assertEqual(result.policy_sha256, self.snapshot.source_sha256)
        self.assertRegex(result.execution_id, r"^[0-9a-f]{32}$")


if __name__ == "__main__":
    unittest.main()
