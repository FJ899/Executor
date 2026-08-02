import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError
from executor.sandbox.spec import SandboxExecutionContext


class SandboxGateFalsificationTest(unittest.TestCase):
    def backend(self):
        return DockerSandboxBackend(executor_policy={"execution": {"external_projects": False}})

    def test_parent_symlink_cannot_disappear_during_source_resolution(self):
        backend = self.backend()
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "root"
            real = root / "real"
            source = real / "source"
            root.mkdir()
            source.mkdir(parents=True)
            (root / "link").symlink_to(real, target_is_directory=True)
            context = SandboxExecutionContext(
                repository="litrgratis-pixel/Executor",
                commit="a" * 40,
                repository_root=root,
                source_dir=root / "link" / "source",
                purpose="EXECUTOR_FIXTURE",
            )
            with patch("executor.sandbox.docker.verify_repository_checkout", return_value=root.resolve()):
                with self.assertRaisesRegex(SandboxExecutionError, "symlink component: link"):
                    backend.authorize(context)

    def test_missing_text_mixed_with_daemon_error_is_not_confirmation(self):
        ambiguous = subprocess.CompletedProcess(
            ["docker", "inspect", "x"],
            1,
            stdout="",
            stderr="Error: No such object: x\nCannot connect to the Docker daemon",
        )
        self.assertFalse(self.backend()._is_confirmed_missing(ambiguous))

    def test_exact_missing_container_message_is_confirmation(self):
        missing = subprocess.CompletedProcess(
            ["docker", "inspect", "x"],
            1,
            stdout="",
            stderr="Error: No such object: x",
        )
        self.assertTrue(self.backend()._is_confirmed_missing(missing))


if __name__ == "__main__":
    unittest.main()
