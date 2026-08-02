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


if __name__ == "__main__":
    unittest.main()
