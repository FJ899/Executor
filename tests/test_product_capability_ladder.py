from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LADDER = ROOT / "EXECUTOR_PRODUCT_CAPABILITY_LADDER.md"
README = ROOT / "README.md"
PURPOSE = ROOT / "CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md"
PR_TEMPLATE = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
CYCLE = ROOT / "docs" / "product_governance" / "EXECUTOR_PRODUCT_WORK_CYCLE_001.md"


class ProductCapabilityLadderTests(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        for path in (LADDER, README, PURPOSE, PR_TEMPLATE, CYCLE):
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), f"missing required governance file: {path}")

    def test_all_product_levels_are_defined_once(self) -> None:
        text = LADDER.read_text(encoding="utf-8")
        levels = re.findall(r"^## P([0-7]) — .+$", text, flags=re.MULTILINE)
        self.assertEqual(levels, [str(index) for index in range(8)])

    def test_each_level_has_required_sections(self) -> None:
        text = LADDER.read_text(encoding="utf-8")
        headings = list(re.finditer(r"^## P([0-7]) — .+$", text, flags=re.MULTILINE))
        required = (
            "### USER OUTCOME",
            "### REQUIRED CAPABILITIES",
            "### REQUIRED EVIDENCE",
            "### EXIT GATE",
            "### NON-GOALS",
            "### STOP CONDITIONS",
        )
        self.assertEqual(len(headings), 8)
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else text.index("# 6. Poziome osie dojrzałości")
            section = text[heading.start():end]
            for required_heading in required:
                with self.subTest(level=heading.group(1), heading=required_heading):
                    self.assertEqual(section.count(required_heading), 1)

    def test_m3_is_not_claimed_as_product_value(self) -> None:
        text = LADDER.read_text(encoding="utf-8")
        self.assertIn(
            "M3 jest rozwojem osi `T`, a nie samodzielnym dowodem wartości produktu.",
            text,
        )
        self.assertIn(
            "M3: T3 TRUST AXIS / LOCKED UNTIL P3 PRODUCT DECISION CONTINUE",
            text,
        )
        self.assertNotRegex(text, r"## P[0-7] — M3\b")

    def test_pr_template_requires_product_alignment(self) -> None:
        text = PR_TEMPLATE.read_text(encoding="utf-8")
        required_fields = (
            "CURRENT PRODUCT LEVEL:",
            "TARGET PRODUCT LEVEL:",
            "LEVEL BLOCKER REMOVED:",
            "USER-VISIBLE CAPABILITY ADDED:",
            "REQUIRED BY CURRENT GATE:",
            "PRIMARY MATURITY AXIS:",
            "AXIS STEP:",
            "EVIDENCE ADDED:",
            "NON-GOALS:",
            "SCOPE EXPANSION:",
        )
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, text)

    def test_authoritative_documents_link_to_ladder(self) -> None:
        for path in (README, PURPOSE):
            with self.subTest(path=path):
                self.assertIn(
                    "EXECUTOR_PRODUCT_CAPABILITY_LADDER.md",
                    path.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
