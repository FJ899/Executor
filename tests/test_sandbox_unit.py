import tempfile
import unittest
from unittest.mock import patch

from executor.sandbox.command_policy import CommandDenied, validate_argv
from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError, SandboxUnavailable
from executor.sandbox.spec import CommandRule, SandboxSpec


class SandboxUnitTest(unittest.TestCase):
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

    def test_structured_command_allowed(self):
        validate_argv(["python", "/source/sandbox_fixture.py", "read_source"], self.spec().command_rules)

    def test_python_c_is_denied(self):
        with self.assertRaises(CommandDenied):
            validate_argv(["python", "-c", "print(1)"], self.spec().command_rules)

    def test_empty_command_denied(self):
        with self.assertRaises(CommandDenied):
            validate_argv([], self.spec().command_rules)

    def test_create_command_contains_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            command = DockerSandboxBackend().build_create_command(
                spec=self.spec(),
                source_dir=temp,
                container_name="test-container",
                argv=["python", "/source/sandbox_fixture.py", "read_source"],
            )
        joined = " ".join(command)
        for marker in ("--network none", "--read-only", "--cap-drop ALL", "no-new-privileges", "--pids-limit 16", "--memory 64m", "--user 65534:65534", "HOME=/nonexistent", "readonly"):
            self.assertIn(marker, joined)
        self.assertNotIn("docker.sock", joined)

    def test_network_capability_rejected(self):
        spec = SandboxSpec(image="x", command_rules=(CommandRule("python"),), network=True)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SandboxExecutionError):
                DockerSandboxBackend().build_create_command(spec=spec, source_dir=temp, container_name="x", argv=["python"])

    def test_secret_capability_rejected(self):
        spec = SandboxSpec(image="x", command_rules=(CommandRule("python"),), secrets=("TOKEN",))
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SandboxExecutionError):
                DockerSandboxBackend().build_create_command(spec=spec, source_dir=temp, container_name="x", argv=["python"])

    def test_home_capability_rejected(self):
        spec = SandboxSpec(image="x", command_rules=(CommandRule("python"),), home_access=True)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(SandboxExecutionError):
                DockerSandboxBackend().build_create_command(spec=spec, source_dir=temp, container_name="x", argv=["python"])

    def test_no_host_fallback_without_docker(self):
        with patch("executor.sandbox.docker.shutil.which", return_value=None):
            with self.assertRaises(SandboxUnavailable):
                DockerSandboxBackend().preflight()


if __name__ == "__main__":
    unittest.main()
