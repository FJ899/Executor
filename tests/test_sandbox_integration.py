import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from executor.sandbox.docker import DockerSandboxBackend
from executor.sandbox.policy_snapshot import load_execution_policy_snapshot
from executor.sandbox.spec import CommandRule, SandboxExecutionContext, SandboxSpec

ROOT = Path(__file__).resolve().parents[1]
CURRENT_EXECUTOR_REPOSITORY = "FJ899/Executor"


@unittest.skipUnless(os.environ.get("RUN_DOCKER_TESTS") == "1", "Docker integration tests are opt-in")
class SandboxIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = os.environ["EXECUTOR_SANDBOX_IMAGE"]
        cls.commit = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        snapshot = load_execution_policy_snapshot(ROOT, commit=cls.commit)
        cls.backend = DockerSandboxBackend(policy_snapshot=snapshot)
        cls.backend.preflight()
        cls.source = Path(__file__).resolve().parent / "fixtures/sandbox"
        cls.context = SandboxExecutionContext(
            repository=CURRENT_EXECUTOR_REPOSITORY,
            commit=cls.commit,
            repository_root=ROOT,
            source_dir=cls.source,
            purpose="EXECUTOR_FIXTURE",
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "output"

    def tearDown(self):
        self.temp.cleanup()

    def spec(self, **changes):
        values = dict(
            image=self.image,
            command_rules=(CommandRule("python", ("/source/sandbox_fixture.py",)),),
            max_cpu=1.0,
            max_memory_mb=64,
            max_disk_mb=8,
            timeout_seconds=4,
            pids_limit=16,
            labels={"creative-os-executor-test": "true"},
        )
        values.update(changes)
        return SandboxSpec(**values)

    def run_action(self, action, **changes):
        return self.backend.run(
            spec=self.spec(**changes),
            context=self.context,
            output_dir=self.output,
            argv=["python", "/source/sandbox_fixture.py", action],
        )

    def test_source_readable(self):
        result = self.run_action("read_source")
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("source-ok", result.stdout)
        self.assertRegex(result.execution_id, r"^[0-9a-f]{32}$")
        self.assertEqual(result.policy_sha256, self.backend.policy_snapshot.source_sha256)

    def test_source_is_read_only(self):
        before = (self.source / "data.txt").read_text()
        result = self.run_action("write_source")
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("SOURCE_READ_ONLY", result.stdout)
        self.assertEqual((self.source / "data.txt").read_text(), before)

    def test_workspace_is_writable(self):
        result = self.run_action("write_workspace")
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("WORKSPACE_WRITTEN:workspace-ok", result.stdout)

    def test_network_is_blocked(self):
        result = self.run_action("network")
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("NETWORK_BLOCKED", result.stdout)

    def test_host_secret_and_home_are_absent(self):
        os.environ["HOST_EXECUTOR_SECRET"] = "must-not-leak"
        try:
            result = self.run_action("environment")
        finally:
            os.environ.pop("HOST_EXECUTOR_SECRET", None)
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("SECRET_ABSENT", result.stdout)
        self.assertIn("HOME=/nonexistent", result.stdout)
        self.assertIn("HOST_HOME_ABSENT", result.stdout)

    def test_timeout_kills_and_cleans_container(self):
        result = self.run_action("sleep", timeout_seconds=1)
        self.assertTrue(result.timed_out)
        self.assertTrue(result.cleanup_verified)

    def test_pid_limit_is_enforced(self):
        result = self.run_action("pids")
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("PIDS_BLOCKED", result.stdout)

    def test_memory_limit_is_enforced(self):
        result = self.run_action("memory", max_memory_mb=48)
        self.assertTrue(result.cleanup_verified)
        self.assertTrue(
            result.exit_code in {0, 137} or "MEMORY_BLOCKED" in result.stdout,
            (result.exit_code, result.stdout, result.stderr),
        )

    def test_disk_limit_is_enforced(self):
        result = self.run_action("disk", max_disk_mb=4)
        self.assertTrue(result.ok, result.stderr)
        self.assertIn("DISK_BLOCKED", result.stdout)

    def test_container_is_removed_after_success(self):
        result = self.run_action("read_source")
        self.assertTrue(result.cleanup_verified)


if __name__ == "__main__":
    unittest.main()
