import os
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path

from executor.pilot_case_001 import (
    PilotCase001DockerSandboxBackend,
    case_001_sandbox_spec,
    execute_case_001,
)
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot

ROOT = Path(__file__).resolve().parents[1]


def _runs_root(case_name: str):
    configured = os.environ.get("PILOT_RUNS_ROOT")
    if configured:
        root = Path(configured).resolve() / case_name
        root.mkdir(parents=True, exist_ok=True)
        return nullcontext(root)
    temporary = tempfile.TemporaryDirectory()
    return _TemporaryRunsRoot(temporary, case_name)


class _TemporaryRunsRoot:
    def __init__(self, temporary, case_name):
        self.temporary = temporary
        self.path = Path(temporary.name) / case_name

    def __enter__(self):
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path

    def __exit__(self, exc_type, exc, tb):
        self.temporary.cleanup()


@unittest.skipUnless(
    os.environ.get("RUN_PILOT_CASE_001") == "1",
    "real CASE-001 pilot is opt-in",
)
class PilotCase001IntegrationTest(unittest.TestCase):
    def test_real_pinned_target_is_acquired_repaired_and_tested_in_docker(self):
        image = os.environ["EXECUTOR_SANDBOX_IMAGE"]
        executor_commit = os.environ.get("EXECUTOR_COMMIT")
        if not executor_commit:
            self.fail("EXECUTOR_COMMIT is required for the real controlled pilot")
        snapshot = load_execution_policy_snapshot(ROOT, commit=executor_commit)
        backend = PilotCase001DockerSandboxBackend(policy_snapshot=snapshot)

        with _runs_root("case-001") as runs_root:
            report = execute_case_001(
                repository_root=None,
                runs_root=runs_root,
                sandbox_backend=backend,
                sandbox_spec=case_001_sandbox_spec(image),
            )

        self.assertEqual(
            report["status"],
            "ACTION_COMPLETED_REVIEW_REQUIRED",
            report,
        )
        self.assertEqual(
            report["changed_paths"],
            ["project_registry/registry.py"],
        )
        self.assertEqual(
            report["source_acquisition"]["input_model"],
            "CONTROLLED_HTTPS_FETCH_V1",
        )
        self.assertEqual(
            report["source_acquisition"]["repository"],
            "litrgratis-pixel/executor-pilot-target",
        )
        combined_logs = "\n".join(
            str(command["stdout"]) + str(command["stderr"])
            for command in report["commands"]
        )
        self.assertIn("Ran 13 tests", combined_logs)
        self.assertIn("OK", combined_logs)


if __name__ == "__main__":
    unittest.main()
