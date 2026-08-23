import subprocess
import tempfile
import unittest
from pathlib import Path

from executor.contracts import ValidationStatus, load_contract
from executor.governance import validate_task_bundle
from executor.repository_identity import repository_identity_from_remote

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "EXECUTOR_POLICY.yaml"
TASK = ROOT / "tasks/examples/EXECUTOR_TASK_FIXTURE-001.yaml"
CURRENT_EXECUTOR_REPOSITORY = "FJ899/Executor"


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


class RepositoryIdentityTest(unittest.TestCase):
    def test_supported_remote_forms_include_host(self):
        self.assertEqual(repository_identity_from_remote("https://github.com/FJ899/Executor.git"), ("github.com", CURRENT_EXECUTOR_REPOSITORY))
        self.assertEqual(repository_identity_from_remote("git@github.com:FJ899/Executor.git"), ("github.com", CURRENT_EXECUTOR_REPOSITORY))
        self.assertEqual(repository_identity_from_remote("https://evil.example/FJ899/Executor.git"), ("evil.example", CURRENT_EXECUTOR_REPOSITORY))

    def test_matching_owner_repo_on_untrusted_host_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            repository_root = Path(temp_name) / "repo"
            repository_root.mkdir()
            run_git(repository_root, "init")
            run_git(repository_root, "config", "user.email", "fixture@example.invalid")
            run_git(repository_root, "config", "user.name", "Fixture")
            (repository_root / "file.txt").write_text("fixture\n", encoding="utf-8")
            run_git(repository_root, "add", "file.txt")
            run_git(repository_root, "commit", "-m", "fixture")
            commit = run_git(repository_root, "rev-parse", "HEAD")
            run_git(repository_root, "remote", "add", "origin", "https://evil.example/FJ899/Executor.git")

            task = load_contract(TASK)
            task["repositories"]["target"]["commit"] = commit
            result = validate_task_bundle(
                task,
                executor_policy=load_contract(POLICY),
                base_dir=ROOT,
                repository_roots={CURRENT_EXECUTOR_REPOSITORY: repository_root},
            )
            self.assertEqual(result.status, ValidationStatus.INVALID)
            self.assertIn("REPOSITORY_ROOT_MISMATCH", {issue.code for issue in result.issues})


if __name__ == "__main__":
    unittest.main()
