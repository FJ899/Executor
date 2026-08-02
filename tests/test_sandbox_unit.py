import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.sandbox.command_policy import CommandDenied, validate_argv
from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError, SandboxUnavailable
from executor.sandbox.spec import CommandRule, SandboxExecutionContext, SandboxSpec


class SandboxUnitTest(unittest.TestCase):
    def policy(self, *, external_projects=False):
        return {"execution": {"external_projects": external_projects}}

    def backend(self, *, external_projects=False):
        return DockerSandboxBackend(executor_policy=self.policy(external_projects=external_projects))

    def spec(self):
        return SandboxSpec(
            image="sha256:test",
            command_rules=(CommandRule("python", ("/source/sandbox_fixture.py",)),),
            max_cpu=1.0,
            max_memory_mb=64,
            max_disk_mb=8,
            timeout_seconds=2,
            pids_limit=16,
            labels={"creative-os-executor-test": "true"},
        )

    def context(self, root, source, *, repository="litrgratis-pixel/Executor", purpose="EXECUTOR_FIXTURE", commit="a" * 40):
        return SandboxExecutionContext(
            repository=repository,
            commit=commit,
            repository_root=Path(root),
            source_dir=Path(source),
            purpose=purpose,
        )

    def completed(self, args, returncode=0, stdout="", stderr=""):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    def test_backend_requires_executor_policy(self):
        with self.assertRaises(SandboxExecutionError):
            DockerSandboxBackend(executor_policy={})

    def test_structured_command_allowed(self):
        validate_argv(["python", "/source/sandbox_fixture.py", "read_source"], self.spec().command_rules)

    def test_python_c_is_denied(self):
        with self.assertRaises(CommandDenied):
            validate_argv(["python", "-c", "print(1)"], self.spec().command_rules)

    def test_empty_command_denied(self):
        with self.assertRaises(CommandDenied):
            validate_argv([], self.spec().command_rules)

    def test_create_command_contains_isolation(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(temp, temp)
            with patch.object(backend, "authorize", return_value=Path(temp)):
                command = backend.build_create_command(
                    spec=self.spec(),
                    context=context,
                    container_name="test-container",
                    argv=["python", "/source/sandbox_fixture.py", "read_source"],
                )
        joined = " ".join(command)
        for marker in ("--network none", "--read-only", "--cap-drop ALL", "no-new-privileges", "--pids-limit 16", "--memory 64m", "--user 65534:65534", "HOME=/nonexistent", "readonly"):
            self.assertIn(marker, joined)
        self.assertNotIn("docker.sock", joined)

    def test_external_project_is_rejected_before_repository_or_docker_calls(self):
        backend = self.backend(external_projects=False)
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(temp, temp, repository="other/Project", purpose="PROJECT")
            with patch("executor.sandbox.docker.verify_repository_checkout") as verify, patch.object(backend, "preflight") as preflight:
                with self.assertRaisesRegex(SandboxExecutionError, "External project execution is disabled"):
                    backend.run(spec=self.spec(), context=context, output_dir=Path(temp) / "output", argv=["python", "/source/sandbox_fixture.py", "read_source"])
                verify.assert_not_called()
                preflight.assert_not_called()

    def test_external_project_can_be_authorized_only_when_policy_allows(self):
        backend = self.backend(external_projects=True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            context = self.context(root, source, repository="other/Project", purpose="PROJECT")
            with patch("executor.sandbox.docker.verify_repository_checkout", return_value=root):
                self.assertEqual(backend.authorize(context), source.resolve())

    def test_fixture_purpose_is_restricted_to_executor_repository(self):
        backend = self.backend(external_projects=True)
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(temp, temp, repository="other/Project", purpose="EXECUTOR_FIXTURE")
            with self.assertRaisesRegex(SandboxExecutionError, "restricted to the Executor"):
                backend.authorize(context)

    def test_source_directory_must_stay_inside_verified_repository(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "root"
            outside = Path(temp) / "outside"
            root.mkdir()
            outside.mkdir()
            context = self.context(root, outside)
            with patch("executor.sandbox.docker.verify_repository_checkout", return_value=root.resolve()):
                with self.assertRaisesRegex(SandboxExecutionError, "escapes the verified repository"):
                    backend.authorize(context)

    def test_network_capability_rejected(self):
        backend = self.backend()
        spec = SandboxSpec(image="x", command_rules=(CommandRule("python"),), network=True)
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(temp, temp)
            with patch.object(backend, "authorize", return_value=Path(temp)):
                with self.assertRaises(SandboxExecutionError):
                    backend.build_create_command(spec=spec, context=context, container_name="x", argv=["python"])

    def test_secret_capability_rejected(self):
        backend = self.backend()
        spec = SandboxSpec(image="x", command_rules=(CommandRule("python"),), secrets=("TOKEN",))
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(temp, temp)
            with patch.object(backend, "authorize", return_value=Path(temp)):
                with self.assertRaises(SandboxExecutionError):
                    backend.build_create_command(spec=spec, context=context, container_name="x", argv=["python"])

    def test_home_capability_rejected(self):
        backend = self.backend()
        spec = SandboxSpec(image="x", command_rules=(CommandRule("python"),), home_access=True)
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(temp, temp)
            with patch.object(backend, "authorize", return_value=Path(temp)):
                with self.assertRaises(SandboxExecutionError):
                    backend.build_create_command(spec=spec, context=context, container_name="x", argv=["python"])

    def test_no_host_fallback_without_docker(self):
        with patch("executor.sandbox.docker.shutil.which", return_value=None):
            with self.assertRaises(SandboxUnavailable):
                self.backend().preflight()

    def test_cleanup_requires_successful_exact_list_query(self):
        backend = self.backend()
        cases = (
            (
                [
                    self.completed(["rm"], 1, stderr="daemon unavailable"),
                    self.completed(["inspect"], 1, stderr="daemon unavailable"),
                    self.completed(["ps"], 1, stderr="daemon unavailable"),
                ],
                False,
            ),
            (
                [
                    self.completed(["rm"], 1, stderr="No such container"),
                    self.completed(["inspect"], 1, stderr="Error: No such object: x"),
                    self.completed(["ps"], 0, stdout=""),
                ],
                True,
            ),
            (
                [self.completed(["rm"], 0), self.completed(["inspect"], 0, stdout="container-json")],
                False,
            ),
        )
        for responses, expected in cases:
            with self.subTest(expected=expected), patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
                verified, _ = backend._cleanup("x")
                self.assertEqual(verified, expected)

    def test_rm_inspect_and_list_failure_cannot_report_cleanup_success(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as temp:
            context = self.context(temp, temp)
            responses = [
                self.completed(["create"], 0),
                self.completed(["start"], 0, stdout="ok"),
                self.completed(["rm"], 1, stderr="daemon unavailable"),
                self.completed(["inspect"], 1, stderr="daemon unavailable"),
                self.completed(["ps"], 1, stderr="daemon unavailable"),
            ]
            with patch.object(backend, "authorize", return_value=Path(temp)), patch.object(backend, "preflight"), patch.object(backend, "build_create_command", return_value=["docker", "create"]), patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
                result = backend.run(spec=self.spec(), context=context, output_dir=Path(temp) / "output", argv=["python", "/source/sandbox_fixture.py", "read_source"], container_name="x")
            self.assertFalse(result.cleanup_verified)
            self.assertFalse(result.ok)
            self.assertIn("CLEANUP_UNVERIFIED", result.stderr)


if __name__ == "__main__":
    unittest.main()
