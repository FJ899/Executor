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

    def test_zero_history_current_recovery_reaches_human_interaction_pointer(self):
        pointer_path = "docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md"
        bootstrap = self.read("CREATIVE_OS_EXECUTOR_BOOTSTRAP_PROMPT.md")
        historical_marker = "## HISTORICAL BOOTSTRAP CONTENT — SUPERSEDED"
        recovery_marker = "For a zero-history current recovery, read instead:"

        self.assertIn(historical_marker, bootstrap)
        current_prefix = bootstrap.split(historical_marker, 1)[0]
        self.assertIn('current_recovery_entry: "README.md"', current_prefix)
        self.assertIn(recovery_marker, current_prefix)
        recovery = current_prefix.split(recovery_marker, 1)[1]
        self.assertIn(f"4. `{pointer_path}`.", recovery)
        self.assertIn("current recovery sequence is complete only after step 4", recovery)
        self.assertLess(recovery.index("`README.md`"), recovery.index(f"`{pointer_path}`"))
        self.assertNotIn("CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md", recovery)

        readme = self.read("README.md")
        truth_marker = "## Jak czytać repo — źródła prawdy"
        next_marker = "## Accepted authority model"
        self.assertIn(truth_marker, readme)
        self.assertIn(next_marker, readme)
        truth_section = readme.split(truth_marker, 1)[1].split(next_marker, 1)[0]
        self.assertIn("Minimalny current zero-history recovery", truth_section)
        self.assertIn(pointer_path, truth_section)
        self.assertIn("AKCJA / GDZIE / ODESŁAĆ", truth_section)
        self.assertNotIn("CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md", truth_section)

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
        marker = "# HISTORICAL BODY — EXACT 2026-08-02 CONTENT"

        self.assertIn(marker, protocol)
        current_prefix, historical_body = protocol.split(marker, 1)
        self.assertIn("HISTORICAL / SUPERSEDED HUMAN-INTERACTION CONTRACT / NOT CURRENT AUTHORITY", current_prefix)
        self.assertIn("historical_source_ref", current_prefix)
        self.assertIn("historical_blob_sha", current_prefix)
        self.assertNotIn('status: "USER APPROVED / AUTHORITATIVE OPERATING CONTRACT"', current_prefix)
        self.assertIn('status: "USER APPROVED / AUTHORITATIVE OPERATING CONTRACT"', historical_body)
        self.assertIn("REKOMENDOWANE DZIAŁANIE", historical_body)
        self.assertIn("DOWÓD ZAKOŃCZENIA", historical_body)

        self.assertNotIn("CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md", current_bundle)
        self.assertIn("docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md", current_bundle)

        self.assertIn('status: "ACTIVE POINTER / NOT SEMANTIC OWNER"', pointer)
        self.assertIn('semantic_owner: "HUMAN"', pointer)
        self.assertIn('canonical_repository: "FJ899/Saddle"', pointer)
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
