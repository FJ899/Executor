import tempfile
import unittest
from pathlib import Path

from executor.pilot_case_001 import case_001_sandbox_spec, execute_case_001
from tests.test_pilot_case_001 import FakeSandboxBackend, PilotRepository


class PilotGitIsolationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fixture = PilotRepository(self.root)
        self.spec = case_001_sandbox_spec("sha256:" + "1" * 64)

    def tearDown(self):
        self.temp.cleanup()

    def test_executable_post_checkout_hook_cannot_run_on_host(self):
        marker = self.root / "host-hook-executed"
        hook = self.fixture.source / ".git/hooks/post-checkout"
        hook.write_text(
            "#!/bin/sh\nprintf executed > " + str(marker) + "\n",
            encoding="utf-8",
        )
        hook.chmod(0o755)

        report = execute_case_001(
            repository_root=self.fixture.source,
            runs_root=self.fixture.runs,
            sandbox_backend=FakeSandboxBackend(),
            sandbox_spec=self.spec,
            contract=self.fixture.contract,
        )

        self.assertEqual(report["status"], "ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertFalse(marker.exists(), "Git post-checkout hook executed outside sandbox")

    def test_rejected_runs_root_does_not_dirty_source(self):
        runs_root = self.fixture.source / "runs"

        report = execute_case_001(
            repository_root=self.fixture.source,
            runs_root=runs_root,
            sandbox_backend=FakeSandboxBackend(),
            sandbox_spec=self.spec,
            contract=self.fixture.contract,
        )

        self.assertEqual(report["status"], "POLICY_BLOCKED")
        self.assertFalse(runs_root.exists())
        self.assertEqual(
            self.fixture._git("status", "--porcelain").stdout,
            "",
        )


if __name__ == "__main__":
    unittest.main()
