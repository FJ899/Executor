import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from executor.cli import main
from executor.contracts import load_contract
from executor.policy import ObjectionKind, PolicyEngine
from executor.repository_access import RepositoryPathError, canonical_repository_path, read_repository_text
from executor.repository_identity import RepositoryIdentityError
from executor.repository_reader import read_wrapped_repository_file

ROOT = Path(__file__).resolve().parents[1]
PROJECT_PATH = ROOT / "project_contracts/executor-self.yaml"
POLICY_PATH = ROOT / "EXECUTOR_POLICY.yaml"
CURRENT_EXECUTOR_REPOSITORY = "JTJ07/Executor"


def git_head() -> str:
    result = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], check=True, capture_output=True, text=True)
    return result.stdout.strip()


class RepositoryAccessTest(unittest.TestCase):
    def project(self):
        return load_contract(PROJECT_PATH)

    def policy(self):
        return load_contract(POLICY_PATH)

    def engine(self):
        return PolicyEngine(self.project(), self.policy())

    def test_normalized_path_is_stable(self):
        self.assertEqual(canonical_repository_path("executor/cli.py"), "executor/cli.py")

    def test_traversal_backslash_absolute_and_unicode_alias_are_rejected(self):
        paths = (
            "executor/../EXECUTOR_POLICY.yaml",
            "executor\\cli.py",
            "/etc/passwd",
            "C:/Windows/system.ini",
            "executor／cli.py",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.engine().check_forbidden_path(path, ["executor/**"]).kind, ObjectionKind.HARD_VETO)

    def test_unsafe_scope_pattern_is_rejected(self):
        result = self.engine().check_forbidden_path("executor/cli.py", ["executor/../**"])
        self.assertEqual(result.kind, ObjectionKind.HARD_VETO)

    def test_new_file_under_regular_parent_is_allowed(self):
        result = self.engine().check_forbidden_path("executor/new_module.py", ["executor/**"], repository_root=ROOT)
        self.assertEqual(result.kind, ObjectionKind.PASS)

    def test_symlink_parent_is_rejected_for_new_file(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "root"
            outside = Path(temp_name) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "link").symlink_to(outside, target_is_directory=True)
            result = self.engine().check_forbidden_path("link/new.py", ["link/**"], repository_root=root)
            self.assertEqual(result.kind, ObjectionKind.HARD_VETO)

    def test_symlink_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name) / "root"
            outside = Path(temp_name) / "outside.txt"
            root.mkdir()
            outside.write_text("outside", encoding="utf-8")
            (root / "link.txt").symlink_to(outside)
            with self.assertRaises(RepositoryPathError):
                read_repository_text(root, "link.txt")

    def test_hardlinked_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            original = root / "original.txt"
            linked = root / "linked.txt"
            original.write_text("same inode", encoding="utf-8")
            os.link(original, linked)
            with self.assertRaisesRegex(RepositoryPathError, "hard-linked"):
                read_repository_text(root, "linked.txt")

    def test_reader_marks_authoritative_and_untrusted_files(self):
        commit = git_head()
        authoritative = read_wrapped_repository_file(
            repository=CURRENT_EXECUTOR_REPOSITORY,
            commit=commit,
            root=ROOT,
            path="EXECUTOR_POLICY.yaml",
            project_contract=self.project(),
        )
        untrusted = read_wrapped_repository_file(
            repository=CURRENT_EXECUTOR_REPOSITORY,
            commit=commit,
            root=ROOT,
            path="tests/fixtures/untrusted_prompt.md",
            project_contract=self.project(),
        )
        self.assertEqual(authoritative["trust"], "trusted_project_instruction")
        self.assertTrue(authoritative["can_instruct_executor"])
        self.assertEqual(untrusted["trust"], "untrusted_data")
        self.assertFalse(untrusted["can_instruct_executor"])

    def test_reader_rejects_false_repository_or_commit_metadata(self):
        with self.assertRaises(RepositoryIdentityError):
            read_wrapped_repository_file(
                repository="someone/Other",
                commit=git_head(),
                root=ROOT,
                path="README.md",
                project_contract=self.project(),
            )
        with self.assertRaises(RepositoryIdentityError):
            read_wrapped_repository_file(
                repository=CURRENT_EXECUTOR_REPOSITORY,
                commit="1" * 40,
                root=ROOT,
                path="README.md",
                project_contract=self.project(),
            )

    def test_executor_cli_command_is_allowed(self):
        objection = self.engine().check_capabilities(command="python -m executor.cli validate-project project_contracts/executor-self.yaml")[0]
        self.assertEqual(objection.kind, ObjectionKind.PASS)

    def test_repository_read_cli_uses_wrapper(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main([
                "repository-read",
                "--project", str(PROJECT_PATH),
                "--policy", str(POLICY_PATH),
                "--base-dir", str(ROOT),
                "--repository", CURRENT_EXECUTOR_REPOSITORY,
                "--commit", git_head(),
                "--root", str(ROOT),
                "--path", "tests/fixtures/untrusted_prompt.md",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["trust"], "untrusted_data")
        self.assertFalse(payload["can_instruct_executor"])


if __name__ == "__main__":
    unittest.main()
