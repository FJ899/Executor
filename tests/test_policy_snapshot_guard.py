import unittest
from pathlib import Path

from executor.sandbox.policy_snapshot import ExecutionPolicyError, ExecutionPolicySnapshot


class PolicySnapshotGuardTest(unittest.TestCase):
    def test_snapshot_cannot_be_constructed_by_caller(self):
        with self.assertRaisesRegex(ExecutionPolicyError, "verified policy file"):
            ExecutionPolicySnapshot(
                repository="litrgratis-pixel/Executor",
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


if __name__ == "__main__":
    unittest.main()
