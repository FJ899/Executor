import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from executor.pilot_case_001 import execute_case_001, case_001_sandbox_spec
from executor.sandbox.pilot import PilotCase001DockerSandboxBackend
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    os.environ.get("RUN_PILOT_CASE_001") == "1",
    "real CASE-001 pilot is opt-in",
)
class PilotCase001IntegrationTest(unittest.TestCase):
    def test_real_pinned_target_is_repaired_and_tested_in_docker(self):
        target = Path(os.environ["PILOT_TARGET_ROOT"]).resolve(strict=True)
        image = os.environ["EXECUTOR_SANDBOX_IMAGE"]
        executor_commit = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        snapshot = load_execution_policy_snapshot(ROOT, commit=executor_commit)
        backend = PilotCase001DockerSandboxBackend(policy_snapshot=snapshot)

        with tempfile.TemporaryDirectory() as temp:
            report = execute_case_001(
                repository_root=target,
                runs_root=Path(temp) / "runs",
                sandbox_backend=backend,
                sandbox_spec=case_001_sandbox_spec(image),
            )
            try:
                self.assertEqual(
                    report["status"],
                    "ACTION_COMPLETED_REVIEW_REQUIRED",
                    report,
                )
                self.assertEqual(
                    report["changed_paths"],
                    ["project_registry/registry.py"],
                )
                combined_logs = "\n".join(
                    str(command["stdout"]) + str(command["stderr"])
                    for command in report["commands"]
                )
                self.assertIn("Ran 13 tests", combined_logs)
                self.assertIn("OK", combined_logs)
            finally:
                worktree = report.get("worktree")
                if worktree and Path(worktree).exists():
                    subprocess.run(
                        [
                            "git",
                            "-C",
                            str(target),
                            "worktree",
                            "remove",
                            "--force",
                            str(worktree),
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                branch = report.get("branch")
                if branch:
                    subprocess.run(
                        ["git", "-C", str(target), "branch", "-D", str(branch)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )


if __name__ == "__main__":
    unittest.main()
