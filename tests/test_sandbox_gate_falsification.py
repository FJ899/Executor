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

    def completed(self, args, returncode=0, stdout="", stderr=""):
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

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

    def test_no_such_text_without_successful_list_query_is_not_proof(self):
        responses = [
            self.completed(["rm"], 0),
            self.completed(["inspect"], 1, stderr="Error: No such object: x"),
            self.completed(["ps"], 1, stderr="Cannot connect to the Docker daemon"),
        ]
        with patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
            verified, detail = self.backend()._cleanup("x")
        self.assertFalse(verified)
        self.assertIn("docker ps verification failed", detail)

    def test_successful_empty_exact_list_query_proves_absence(self):
        responses = [
            self.completed(["rm"], 0),
            self.completed(["inspect"], 1, stderr="Error: No such object: x"),
            self.completed(["ps"], 0, stdout=""),
        ]
        with patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
            verified, _ = self.backend()._cleanup("x")
        self.assertTrue(verified)

    def test_unexpected_name_from_exact_filter_is_not_proof(self):
        responses = [
            self.completed(["rm"], 0),
            self.completed(["inspect"], 1, stderr="Error: No such object: x"),
            self.completed(["ps"], 0, stdout="another-container\n"),
        ]
        with patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
            verified, detail = self.backend()._cleanup("x")
        self.assertFalse(verified)
        self.assertIn("unexpected names", detail)


if __name__ == "__main__":
    unittest.main()
