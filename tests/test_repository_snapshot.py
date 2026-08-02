import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from executor.policy import wrap_repository_content
from executor.repository_reader import read_wrapped_repository_file
from executor.repository_snapshot import RepositorySnapshotError, verify_source_tree, verify_worktree_file
from executor.sandbox.docker import DockerSandboxBackend, SandboxExecutionError
from executor.sandbox.policy_snapshot import ExecutionPolicyError, load_execution_policy_snapshot
from executor.sandbox.spec import SandboxExecutionContext


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)
    return result.stdout.strip()


def create_repository(root: Path, *, external_projects=False) -> str:
    root.mkdir()
    run_git(root, "init")
    run_git(root, "config", "user.email", "fixture@example.invalid")
    run_git(root, "config", "user.name", "Fixture")
    policy = {
        "schema_version": "executor-policy/1.0",
        "execution": {
            "external_projects": external_projects,
            "auto_merge": False,
            "default_network": False,
            "default_secrets": [],
        },
    }
    (root / "EXECUTOR_POLICY.yaml").write_text(json.dumps(policy), encoding="utf-8")
    (root / ".gitignore").write_text("source/ignored.tmp\n", encoding="utf-8")
    source = root / "source"
    source.mkdir()
    (source / "program.py").write_text("print('committed')\n", encoding="utf-8")
    (source / "data.txt").write_text("committed\n", encoding="utf-8")
    run_git(root, "add", "EXECUTOR_POLICY.yaml", ".gitignore", "source")
    run_git(root, "commit", "-m", "fixture")
    run_git(root, "remote", "add", "origin", "https://github.com/litrgratis-pixel/Executor.git")
    return run_git(root, "rev-parse", "HEAD")


class RepositorySnapshotTest(unittest.TestCase):
    def test_policy_snapshot_requires_committed_policy_blob(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repo"
            commit = create_repository(root)
            snapshot = load_execution_policy_snapshot(root, commit=commit)
            self.assertFalse(snapshot.external_projects)
            (root / "EXECUTOR_POLICY.yaml").write_text(
                '{"schema_version":"executor-policy/1.0","execution":{"external_projects":true,"auto_merge":false,"default_network":false,"default_secrets":[]}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ExecutionPolicyError, "differs from committed blob"):
                load_execution_policy_snapshot(root, commit=commit)

    def test_source_tree_matches_commit(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repo"
            commit = create_repository(root)
            verified = verify_source_tree(root, commit=commit, source_dir=root / "source")
            self.assertEqual(verified, ("source/data.txt", "source/program.py"))

    def test_modified_tracked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repo"
            commit = create_repository(root)
            (root / "source/program.py").write_text("print('modified')\n", encoding="utf-8")
            with self.assertRaisesRegex(RepositorySnapshotError, "differs from committed blob"):
                verify_source_tree(root, commit=commit, source_dir=root / "source")

    def test_missing_tracked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repo"
            commit = create_repository(root)
            (root / "source/data.txt").unlink()
            with self.assertRaisesRegex(RepositorySnapshotError, "missing="):
                verify_source_tree(root, commit=commit, source_dir=root / "source")

    def test_untracked_and_ignored_source_is_rejected(self):
        for name in ("untracked.txt", "ignored.tmp"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp_name:
                root = Path(temp_name) / "repo"
                commit = create_repository(root)
                (root / f"source/{name}").write_text("extra\n", encoding="utf-8")
                with self.assertRaisesRegex(RepositorySnapshotError, "additional="):
                    verify_source_tree(root, commit=commit, source_dir=root / "source")

    def test_wrapped_repository_read_rejects_dirty_worktree_file(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repo"
            commit = create_repository(root)
            project = {
                "authoritative_sources": [
                    {"path": "source/data.txt", "role": "evidence"},
                ]
            }
            clean = read_wrapped_repository_file(
                repository="litrgratis-pixel/Executor",
                commit=commit,
                root=root,
                path="source/data.txt",
                project_contract=project,
            )
            self.assertEqual(clean["trust"], "trusted_project_data")
            (root / "source/data.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(RepositorySnapshotError, "differs from committed blob"):
                read_wrapped_repository_file(
                    repository="litrgratis-pixel/Executor",
                    commit=commit,
                    root=root,
                    path="source/data.txt",
                    project_contract=project,
                )

    def test_sandbox_authorization_rejects_dirty_source_before_docker(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "repo"
            commit = create_repository(root, external_projects=True)
            snapshot = load_execution_policy_snapshot(root, commit=commit)
            backend = DockerSandboxBackend(policy_snapshot=snapshot)
            (root / "source/program.py").write_text("print('dirty')\n", encoding="utf-8")
            context = SandboxExecutionContext(
                repository="other/Project",
                commit="1" * 40,
                repository_root=root,
                source_dir=root / "source",
                purpose="PROJECT",
            )
            with patch("executor.sandbox.docker.verify_repository_checkout", return_value=root.resolve()), patch.object(backend, "preflight") as preflight:
                with self.assertRaisesRegex(SandboxExecutionError, "does not match the locked commit"):
                    backend.run(spec=None, context=context, output_dir=root / "output", argv=[])
                preflight.assert_not_called()


if __name__ == "__main__":
    unittest.main()
