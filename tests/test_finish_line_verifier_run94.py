from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "tools" / "finish_line_verifier" / "verify_run94.py"
spec = importlib.util.spec_from_file_location("finish_line_verifier_run94", VERIFIER)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


class Run94VerifierTests(unittest.TestCase):
    def test_candidate_verdict_is_non_authoritative(self):
        self.assertEqual(module.AUTH, "IGNORED_FOR_AUTHORITY")

    def test_provider_timestamp_at_expiry_is_rejected(self):
        receipt = {
            "state": "FINAL",
            "terminal_success": True,
            "provider_created_at": "2026-08-20T18:00:00Z",
            "not_after": "2026-08-20T18:00:00Z",
        }
        with self.assertRaises(module.base.VerificationError):
            module.fresh(receipt, "effect")

    def test_change_stability_allows_only_dependency_and_ref_rebinding(self):
        old = "if: refs/heads/phase-b/p4-repeatable-executor-1.0\nif: refs/heads/phase-b/p4-repeatable-executor-1.0\nPyYAML==6.0.2\n"
        new = "if: refs/heads/preflight/p4-pyyaml-6.0.3-ref-binding\nif: refs/heads/preflight/p4-pyyaml-6.0.3-ref-binding\nPyYAML==6.0.3\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / "old.yml", root / "new.yml"
            a.write_text(old); b.write_text(new)
            exp = {
                "baseline_workflow_sha256": module.sha_file(a),
                "current_workflow_sha256": module.sha_file(b),
                "old_dependency": "PyYAML==6.0.2",
                "new_dependency": "PyYAML==6.0.3",
                "historical_ref": "refs/heads/phase-b/p4-repeatable-executor-1.0",
                "dedicated_ref": "refs/heads/preflight/p4-pyyaml-6.0.3-ref-binding",
                "old_image_id": "sha256:old",
                "new_image_id": "sha256:new",
                "historical_scriptops_patch_sha256": "a",
                "historical_reconstructor_patch_sha256": "b",
            }
            result = module.change_stability(a, b, exp, {"scriptops": {"patch_sha256": "a"}, "reconstructor": {"patch_sha256": "b"}})
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["task_semantics_change"])
            self.assertFalse(result["capability_change"])

    def test_review_binding_requires_exact_approved_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reviewed = root / "file.py"; reviewed.write_text("x = 1\n")
            reviews = root / "reviews.json"
            reviews.write_text(json.dumps([{"id": 7, "state": "APPROVED", "commit_id": "abc", "user": {"login": "JTJ07"}}]))
            exp = {"review_id": 7, "reviewed_head": "abc", "reviewer_login": "JTJ07", "reviewed_file_sha256": module.sha_file(reviewed), "repository": "R", "pr_number": 1}
            self.assertEqual(module.review_binding(reviews, reviewed, exp, 3)["coverage"], 3)
            exp["reviewed_head"] = "def"
            with self.assertRaises(module.base.VerificationError):
                module.review_binding(reviews, reviewed, exp, 3)


if __name__ == "__main__":
    unittest.main()
