import contextlib
import io
import json
import unittest
from unittest.mock import patch, sentinel

from executor import pilot_cli


class PilotCliTest(unittest.TestCase):
    def test_case_002_dispatches_only_to_case_002_pipeline(self):
        report = {
            "status": "ACTION_COMPLETED_REVIEW_REQUIRED",
            "task_id": "CASE-002",
        }
        argv = [
            "--case",
            "002",
            "--repository-root",
            "/target",
            "--runs-root",
            "/runs",
            "--executor-root",
            "/executor",
            "--executor-commit",
            "a" * 40,
            "--image",
            "sha256:" + "b" * 64,
        ]

        with (
            patch.object(
                pilot_cli,
                "load_execution_policy_snapshot",
                return_value=sentinel.snapshot,
            ) as load_snapshot,
            patch.object(
                pilot_cli,
                "PilotCase002DockerSandboxBackend",
                return_value=sentinel.backend,
            ) as backend_class,
            patch.object(
                pilot_cli,
                "case_002_sandbox_spec",
                return_value=sentinel.spec,
            ) as build_spec,
            patch.object(
                pilot_cli,
                "execute_case_002",
                return_value=report,
            ) as execute_case_002,
            patch.object(pilot_cli, "execute_case_001") as execute_case_001,
            patch.object(pilot_cli, "execute_case_003") as execute_case_003,
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = pilot_cli.main(argv)

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue()), report)
        load_snapshot.assert_called_once_with(
            "/executor",
            commit="a" * 40,
        )
        backend_class.assert_called_once_with(
            policy_snapshot=sentinel.snapshot,
            contract=pilot_cli.CASE_002_CONTRACT,
        )
        build_spec.assert_called_once_with("sha256:" + "b" * 64)
        execute_case_002.assert_called_once_with(
            repository_root="/target",
            runs_root="/runs",
            sandbox_backend=sentinel.backend,
            sandbox_spec=sentinel.spec,
        )
        execute_case_001.assert_not_called()
        execute_case_003.assert_not_called()

    def test_case_003_dispatches_only_to_case_003_pipeline(self):
        report = {
            "status": "ACTION_COMPLETED_REVIEW_REQUIRED",
            "task_id": "CASE-003",
        }
        argv = [
            "--case",
            "003",
            "--repository-root",
            "/target-003",
            "--runs-root",
            "/runs-003",
            "--executor-root",
            "/executor",
            "--executor-commit",
            "c" * 40,
            "--image",
            "sha256:" + "d" * 64,
        ]

        with (
            patch.object(
                pilot_cli,
                "load_execution_policy_snapshot",
                return_value=sentinel.snapshot,
            ) as load_snapshot,
            patch.object(
                pilot_cli,
                "PilotCase003DockerSandboxBackend",
                return_value=sentinel.backend,
            ) as backend_class,
            patch.object(
                pilot_cli,
                "case_003_sandbox_spec",
                return_value=sentinel.spec,
            ) as build_spec,
            patch.object(
                pilot_cli,
                "execute_case_003",
                return_value=report,
            ) as execute_case_003,
            patch.object(pilot_cli, "execute_case_001") as execute_case_001,
            patch.object(pilot_cli, "execute_case_002") as execute_case_002,
        ):
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = pilot_cli.main(argv)

        self.assertEqual(result, 0)
        self.assertEqual(json.loads(stdout.getvalue()), report)
        load_snapshot.assert_called_once_with(
            "/executor",
            commit="c" * 40,
        )
        backend_class.assert_called_once_with(
            policy_snapshot=sentinel.snapshot,
            contract=pilot_cli.CASE_003_CONTRACT,
        )
        build_spec.assert_called_once_with("sha256:" + "d" * 64)
        execute_case_003.assert_called_once_with(
            repository_root="/target-003",
            runs_root="/runs-003",
            sandbox_backend=sentinel.backend,
            sandbox_spec=sentinel.spec,
        )
        execute_case_001.assert_not_called()
        execute_case_002.assert_not_called()


if __name__ == "__main__":
    unittest.main()
