import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot
from executor.sandbox.spec import SandboxExecutionContext

ROOT = Path(__file__).resolve().parents[1]
EXECUTION_ID = "a" * 32


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


class SandboxGateFalsificationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        commit = run_git(ROOT, "rev-parse", "HEAD")
        cls.backend_value = DockerSandboxBackend(
            policy_snapshot=load_execution_policy_snapshot(ROOT, commit=commit)
        )

    def backend(self):
        return self.backend_value

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
                repository="other/Project",
                commit="a" * 40,
                repository_root=root,
                source_dir=root / "link" / "source",
                purpose="PROJECT",
            )
            with patch.object(
                backend,
                "_authoritative_policy",
                return_value=SimpleNamespace(external_projects=True),
            ), patch(
                "executor.sandbox.docker.verify_repository_checkout",
                return_value=root.resolve(),
            ):
                with self.assertRaisesRegex(SandboxExecutionError, "symlink component: link"):
                    backend.authorize(context)

    def test_no_such_text_without_successful_list_query_is_not_proof(self):
        responses = [
            self.completed(["inspect"], 1, stderr="Error: No such object: x"),
            self.completed(["ps"], 1, stderr="Cannot connect to the Docker daemon"),
        ]
        with patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
            verified, detail = self.backend()._cleanup("x", EXECUTION_ID)
        self.assertFalse(verified)
        self.assertIn("docker ps verification failed", detail)

    def test_successful_empty_exact_list_query_proves_absence(self):
        responses = [
            self.completed(["inspect"], 1, stderr="Error: No such object: x"),
            self.completed(["ps"], 0, stdout=""),
        ]
        with patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
            verified, _ = self.backend()._cleanup("x", EXECUTION_ID)
        self.assertTrue(verified)

    def test_unexpected_name_from_exact_filter_is_not_proof(self):
        responses = [
            self.completed(["inspect"], 1, stderr="Error: No such object: x"),
            self.completed(["ps"], 0, stdout="another-container\n"),
        ]
        with patch("executor.sandbox.docker.subprocess.run", side_effect=responses):
            verified, detail = self.backend()._cleanup("x", EXECUTION_ID)
        self.assertFalse(verified)
        self.assertIn("ownership could not be verified", detail)


if __name__ == "__main__":
    unittest.main()
