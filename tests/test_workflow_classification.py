from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "governance" / "WORKFLOW_CLASSIFICATION.json"
WORKFLOWS = ROOT / ".github" / "workflows"


class WorkflowClassificationTests(unittest.TestCase):
    def test_every_workflow_has_exactly_one_classification(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        declared = set(manifest["workflows"])
        actual = {
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in WORKFLOWS.iterdir()
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        }
        self.assertEqual(declared, actual)
        allowed = {
            "ACTIVE_PRODUCTION_FOUNDATION",
            "ACTIVE_TEST",
            "HISTORICAL_EVIDENCE",
            "OBSOLETE",
        }
        for path, record in manifest["workflows"].items():
            with self.subTest(path=path):
                self.assertIn(record["classification"], allowed)
                self.assertTrue(record["reason"])

    def test_active_production_workflows_are_free_of_historical_bindings(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        forbidden = ("JTJ07/", "preflight/", "--issue 65", "--issue 66")
        for relative, record in manifest["workflows"].items():
            if record["classification"] != "ACTIVE_PRODUCTION_FOUNDATION":
                continue
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(path=relative):
                for token in forbidden:
                    self.assertNotIn(token, text)

    def test_historical_p4_one_shot_is_not_product_foundation(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["workflows"][".github/workflows/p4-real-pilots-one-shot.yml"]["classification"],
            "HISTORICAL_EVIDENCE",
        )


if __name__ == "__main__":
    unittest.main()
