import json
import tempfile
import unittest
from pathlib import Path

from executor.self_test import run_executor_self_test


class ExecutorSelfTestTest(unittest.TestCase):
    def test_executor_self_test_001_reaches_pass_without_exposing_holdout(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report_path = root / "report.json"
            report = run_executor_self_test(
                root / "work",
                executor_commit="7" * 40,
                output_path=report_path,
            )
            self.assertEqual(
                report["verdict"], "LOCAL_PASS_PENDING_EXTERNAL_ATTESTATION"
            )
            self.assertFalse(report["final_acceptance_eligible"])
            self.assertEqual(report["final_state"], "PASS")
            self.assertEqual(report["authorization"]["winner_count"], 1)
            self.assertEqual(report["authorization"]["concurrent_attempts"], 32)
            self.assertEqual(report["main_before"], report["main_after"])
            self.assertTrue(all(report["controls"].values()))
            self.assertTrue(all(report["tamper_controls"].values()))
            self.assertFalse(report["holdout"]["content_exposure_observed"])
            self.assertFalse(report["holdout"]["independent_certification"])
            serialized = report_path.read_text(encoding="utf-8")
            self.assertNotIn("assertions", serialized)
            self.assertNotIn("authentication_key", serialized)
            self.assertEqual(json.loads(serialized)["test_id"], "EXECUTOR_SELF_TEST-001")


if __name__ == "__main__":
    unittest.main()
