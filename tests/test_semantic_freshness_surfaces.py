import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class SemanticFreshnessSurfaceTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8")

    def test_historical_bootstrap_cannot_present_m0_m1_as_current_route(self):
        text = self.read("CREATIVE_OS_EXECUTOR_BOOTSTRAP_PROMPT.md")
        self.assertIn("HISTORICAL / SUPERSEDED / NOT CURRENT BOOTSTRAP", text)
        self.assertIn("current_recovery_entry: \"README.md\"", text)
        self.assertIn("ACTIVE PRODUCT COMPLETION GATE: NONE", text)
        self.assertIn("HISTORICAL BOOTSTRAP CONTENT — SUPERSEDED", text)

    def test_charter_recovers_current_run94_and_ownership_boundary(self):
        text = self.read("EXECUTOR_CHARTER.md")
        self.assertIn("P4 REPEATABLE EXECUTOR 1.0", text)
        self.assertIn("G-01–G-18: PASS", text)
        self.assertIn("EXTERNAL / BASE INTELLIGENCE", text)
        self.assertIn("operational framing + HOW + cognitive routing", text)
        self.assertIn("EXECUTOR\n→ authorized consequential effects", text)
        self.assertNotIn(
            "M0–M2B są fundamentami w trakcie napraw i ponownej weryfikacji po audycie baseline",
            text,
        )

    def test_v02_build_instruction_is_historical_not_current_authority(self):
        text = self.read("CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md")
        self.assertIn("HISTORICAL / SUPERSEDED IMPLEMENTATION INSTRUCTION / NOT CURRENT BOOTSTRAP", text)
        self.assertIn("not a current implementation contract", text)
        self.assertIn("EXTERNAL / BASE INTELLIGENCE", text)
        self.assertIn("authorized consequential effects", text)
        self.assertIn("historical_source_ref", text)

        current_bundle = self.read("project_contracts/executor-self.yaml")
        self.assertNotIn("CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md", current_bundle)
        self.assertIn("CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md", current_bundle)
        self.assertIn("README.md", current_bundle)

    def test_historical_work_protocol_cannot_be_current_human_interaction_authority(self):
        protocol = self.read("CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md")
        pointer = self.read("docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md")
        current_bundle = self.read("project_contracts/executor-self.yaml")

        self.assertIn("HISTORICAL / SUPERSEDED HUMAN-INTERACTION CONTRACT / NOT CURRENT AUTHORITY", protocol)
        self.assertIn("historical_source_ref", protocol)
        self.assertIn("historical_blob_sha", protocol)
        self.assertNotIn('status: "USER APPROVED / AUTHORITATIVE OPERATING CONTRACT"', protocol)

        self.assertNotIn("CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md", current_bundle)
        self.assertIn("docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md", current_bundle)

        self.assertIn('status: "ACTIVE POINTER / NOT SEMANTIC OWNER"', pointer)
        self.assertIn('semantic_owner: "HUMAN"', pointer)
        self.assertIn('canonical_repository: "JTJ07/Saddle"', pointer)
        self.assertIn('canonical_path: "docs/HUMAN_OPERATING_CONTRACT.md"', pointer)
        self.assertIn("AKCJA\nGDZIE\nODESŁAĆ", pointer)
        self.assertIn("CAPABILITY != PERMISSION", pointer)

    def test_product_purpose_separates_durable_mission_from_current_role_placement(self):
        text = self.read("CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md")
        self.assertIn("AUTHORITATIVE DURABLE PRODUCT PURPOSE", text)
        self.assertIn("ROLE PLACEMENT RECONCILED", text)
        self.assertIn("GINSENG → decision-space understanding", text)
        self.assertIn("EXTERNAL / BASE INTELLIGENCE → operational framing + HOW + cognitive routing", text)
        self.assertIn("EXECUTOR → authorized consequential effects", text)
        self.assertIn("CURRENT RUN94 HUMAN-ACCEPTED IMPLEMENTATION: 3cd0c8d747fef06f82c01cdab8449c7c8a100038", text)
        self.assertNotIn("CURRENT HUMAN-SELECTED TARGET: P4 REPEATABLE EXECUTOR 1.0 / PHASE B CANDIDATE", text)


if __name__ == "__main__":
    unittest.main()
