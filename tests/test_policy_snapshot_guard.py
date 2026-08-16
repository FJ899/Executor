import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from executor.sandbox.policy_snapshot import (
    ExecutionPolicyError,
    ExecutionPolicySnapshot,
    load_execution_policy_snapshot,
)


CURRENT_EXECUTOR_REPOSITORY = "JTJ07/Executor"
PREVIOUS_EXECUTOR_REPOSITORY = "litrgratis-pixel/Executor"


class PolicySnapshotGuardTest(unittest.TestCase):
    def test_snapshot_cannot_be_constructed_by_caller(self):
        with self.assertRaisesRegex(ExecutionPolicyError, "verified policy file"):
            ExecutionPolicySnapshot(
                repository=CURRENT_EXECUTOR_REPOSITORY,
                commit="1" * 40,
                repository_root=Path("."),
                source_path="EXECUTOR_POLICY.yaml",
                source_sha256="2" * 64,
                external_projects=True,
                auto_merge=True,
                default_network=True,
                default_secrets=("FORGED",),
                _proof=object(),
            )

    def make_policy_repo(self, execution, repository=CURRENT_EXECUTOR_REPOSITORY):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(root), "config", "user.name", "Policy Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "config",
                "user.email",
                "policy@example.invalid",
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "remote",
                "add",
                "origin",
                f"https://github.com/{repository}.git",
            ],
            check=True,
        )
        document = {
            "schema_version": "executor-policy/1.0",
            "execution": execution,
        }
        (root / "EXECUTOR_POLICY.yaml").write_text(
            json.dumps(document) + "\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "commit", "-q", "-m", "policy"],
            check=True,
        )
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        return temp, root, commit

    def test_default_self_identity_is_current_repository(self):
        execution = {
            "external_projects": False,
            "controlled_external_fixtures": [],
            "auto_merge": False,
            "default_network": False,
            "default_secrets": [],
        }
        temp, root, commit = self.make_policy_repo(execution)
        self.addCleanup(temp.cleanup)

        snapshot = load_execution_policy_snapshot(root, commit=commit)

        self.assertEqual(snapshot.repository, CURRENT_EXECUTOR_REPOSITORY)

    def test_previous_owner_is_rejected_by_current_self_identity(self):
        execution = {
            "external_projects": False,
            "controlled_external_fixtures": [],
            "auto_merge": False,
            "default_network": False,
            "default_secrets": [],
        }
        temp, root, commit = self.make_policy_repo(
            execution,
            repository=PREVIOUS_EXECUTOR_REPOSITORY,
        )
        self.addCleanup(temp.cleanup)

        with self.assertRaisesRegex(
            ExecutionPolicyError,
            "expected JTJ07/Executor",
        ):
            load_execution_policy_snapshot(root, commit=commit)

    def test_controlled_external_fixture_is_exact_policy_authority(self):
        execution = {
            "external_projects": False,
            "controlled_external_fixtures": [
                {
                    "task": "GP001-FIX-FAILING-TEST-CASE-001",
                    "repository": "litrgratis-pixel/executor-pilot-target",
                    "commit": "3934a94a5eebf750079200589d6dc40e024d44a0",
                }
            ],
            "auto_merge": False,
            "default_network": False,
            "default_secrets": [],
        }
        temp, root, commit = self.make_policy_repo(execution)
        self.addCleanup(temp.cleanup)

        snapshot = load_execution_policy_snapshot(root, commit=commit)

        self.assertFalse(snapshot.external_projects)
        self.assertTrue(
            snapshot.authorizes_controlled_external_fixture(
                task="GP001-FIX-FAILING-TEST-CASE-001",
                repository="litrgratis-pixel/executor-pilot-target",
                commit="3934a94a5eebf750079200589d6dc40e024d44a0",
            )
        )
        for task, repository, fixture_commit in (
            (
                "GP001-DIFFERENT-TASK",
                "litrgratis-pixel/executor-pilot-target",
                "3934a94a5eebf750079200589d6dc40e024d44a0",
            ),
            (
                "GP001-FIX-FAILING-TEST-CASE-001",
                "litrgratis-pixel/not-the-fixture",
                "3934a94a5eebf750079200589d6dc40e024d44a0",
            ),
            (
                "GP001-FIX-FAILING-TEST-CASE-001",
                "litrgratis-pixel/executor-pilot-target",
                "1" * 40,
            ),
        ):
            with self.subTest(task=task, repository=repository, commit=fixture_commit):
                self.assertFalse(
                    snapshot.authorizes_controlled_external_fixture(
                        task=task,
                        repository=repository,
                        commit=fixture_commit,
                    )
                )

    def test_malformed_controlled_external_fixture_is_rejected(self):
        execution = {
            "external_projects": False,
            "controlled_external_fixtures": [
                {
                    "task": "GP001-FIX-FAILING-TEST-CASE-001",
                    "repository": "not-owner-name",
                    "commit": "3934a94a5eebf750079200589d6dc40e024d44a0",
                }
            ],
            "auto_merge": False,
            "default_network": False,
            "default_secrets": [],
        }
        temp, root, commit = self.make_policy_repo(execution)
        self.addCleanup(temp.cleanup)

        with self.assertRaisesRegex(ExecutionPolicyError, "owner/name"):
            load_execution_policy_snapshot(root, commit=commit)

    def test_bounded_pilot_profile_is_exact_and_draft_only(self):
        execution = {
            "external_projects": False,
            "controlled_external_fixtures": [],
            "bounded_pilot_repositories": [
                {
                    "repository": "JTJ07/scriptops",
                    "max_production_files": 3,
                    "draft_pr_only": True,
                }
            ],
            "auto_merge": False,
            "default_network": False,
            "default_secrets": [],
        }
        temp, root, commit = self.make_policy_repo(execution)
        self.addCleanup(temp.cleanup)
        snapshot = load_execution_policy_snapshot(root, commit=commit)
        profile = snapshot.bounded_pilot_profile(repository="JTJ07/scriptops")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.max_production_files, 3)
        self.assertTrue(profile.draft_pr_only)
        self.assertIsNone(
            snapshot.bounded_pilot_profile(repository="JTJ07/not-authorized")
        )

    def test_bounded_pilot_cannot_enable_more_than_three_files_or_merge(self):
        for maximum, draft_only in ((4, True), (3, False)):
            with self.subTest(maximum=maximum, draft_only=draft_only):
                execution = {
                    "external_projects": False,
                    "controlled_external_fixtures": [],
                    "bounded_pilot_repositories": [
                        {
                            "repository": "JTJ07/scriptops",
                            "max_production_files": maximum,
                            "draft_pr_only": draft_only,
                        }
                    ],
                    "auto_merge": False,
                    "default_network": False,
                    "default_secrets": [],
                }
                temp, root, commit = self.make_policy_repo(execution)
                self.addCleanup(temp.cleanup)
                with self.assertRaises(ExecutionPolicyError):
                    load_execution_policy_snapshot(root, commit=commit)


if __name__ == "__main__":
    unittest.main()
