from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LADDER = ROOT / "EXECUTOR_PRODUCT_CAPABILITY_LADDER.md"
CYCLE = ROOT / "docs" / "product_governance" / "EXECUTOR_PRODUCT_WORK_CYCLE_001.md"


class ProductWorkCycle001Tests(unittest.TestCase):
    def test_cycle_is_present_and_bound_to_p1(self) -> None:
        text = CYCLE.read_text(encoding="utf-8")
        self.assertIn("cycle_id: PRODUCT-WORK-CYCLE-001", text)
        self.assertIn("P1 — CONTROLLED PILOT RUNTIME", text)
        self.assertIn("3f6e4196af4b9144ceaaba08f2b6637acdc1698d", text)
        self.assertIn("901e78590a446544a5d25abcecddd3e282072500", text)
        self.assertIn("REQUIRED O1 ENABLER / REVIEW BEFORE MERGE", text)

    def test_cycle_does_not_claim_p1_acceptance(self) -> None:
        text = CYCLE.read_text(encoding="utf-8")
        self.assertIn("PRODUCT LEVEL ADVANCED:\nNO", text)
        self.assertIn("Runda ustanawia governance, ale nie ogłasza P1.", text)
        self.assertIn("DRAFT / REWORK / EXACT-SHA CI MISSING", text)
        self.assertNotIn("P1: ACHIEVED", text)

    def test_ladder_is_authoritative(self) -> None:
        ladder = LADDER.read_text(encoding="utf-8")
        self.assertIn(
            "status: USER APPROVED / AUTHORITATIVE PRODUCT GOVERNANCE",
            ladder,
        )
        self.assertIn(
            "CURRENT MAIN PRODUCT LEVEL: P0 — FOUNDATION / ACHIEVED IN DECLARED SCOPE",
            ladder,
        )
        self.assertIn(
            "CURRENT TARGET: P1 — CONTROLLED PILOT RUNTIME",
            ladder,
        )

    def test_cycle_binds_p0_achievement_to_exact_evidence(self) -> None:
        text = CYCLE.read_text(encoding="utf-8")
        for value in (
            "b092a85e82eb81ec6dc7db4a7064409c6c383359",
            "#16",
            "30755381646",
            "docs/M0_M2B_FINAL_ENTRY_GATE_2026-08-02.md",
            "ACCEPTED THROUGH MERGE OF PR #16",
        ):
            with self.subTest(value=value):
                self.assertIn(value, text)


if __name__ == "__main__":
    unittest.main()
