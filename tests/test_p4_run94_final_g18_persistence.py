from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_IMPLEMENTATION = "3cd0c8d747fef06f82c01cdab8449c7c8a100038"
ACCEPTED_TREE = "c739aaa989a15eaed65996d7a0b5242a0ec26d7e"
CONSEQUENTIAL_RUN = "32404181188"
TRUSTED_RUN = "32407901358"
MAIN_AT_ACCEPTANCE = "a7fc272e09a2ffb5c06a98e26ed6ef9667cd4f89"
NEW_RECORD = "docs/governance/EXECUTOR_1_0_FINAL_HUMAN_ACCEPTANCE_RECORD_2026-08-20.md"
HISTORICAL_RECORD = "docs/governance/EXECUTOR_1_0_FINAL_COMPLETION_RECORD_2026-08-18.md"
HISTORICAL_CLOSURE = "evidence/phase-c/EXECUTOR_1_0_POST_INTEGRATION_CLOSURE_2026-08-18.md"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class FinalG18PersistenceTests(unittest.TestCase):
    def test_new_record_binds_exact_run94_acceptance(self) -> None:
        text = read(NEW_RECORD)
        for value in (
            ACCEPTED_IMPLEMENTATION,
            ACCEPTED_TREE,
            CONSEQUENTIAL_RUN,
            TRUSTED_RUN,
            MAIN_AT_ACCEPTANCE,
            "G-18: PASS",
            "PROJECT COMPLETION: PASS",
            "EXECUTOR 1.0: ACCEPT",
        ):
            self.assertIn(value, text)
        self.assertIn("TA DECYZJA NIE AUTORYZUJE RELEASE, DEPLOY, TAG ANI DALSZEGO MERGE.", text)
        self.assertIn('release_authority: "NONE"', text)
        self.assertIn('deploy_authority: "NONE"', text)
        self.assertIn('tag_authority: "NONE"', text)
        self.assertIn('further_merge_authority: "NONE"', text)

    def test_current_status_surfaces_point_to_run94_record(self) -> None:
        for path in ("README.md", "PROJECT_COMPLETION_MAP.md", "docs/governance/DOCUMENT_AUTHORITY.md"):
            text = read(path)
            self.assertIn(NEW_RECORD, text, path)
            self.assertIn(ACCEPTED_IMPLEMENTATION, text, path)
            self.assertIn("G-01–G-18: PASS", text, path)
            self.assertIn("PROJECT COMPLETION: PASS", text, path)

    def test_historical_2026_08_18_records_are_preserved_as_history(self) -> None:
        for path in ("README.md", "docs/governance/DOCUMENT_AUTHORITY.md", NEW_RECORD):
            text = read(path)
            self.assertIn(HISTORICAL_RECORD, text, path)
            self.assertIn(HISTORICAL_CLOSURE, text, path)
        completion_map = read("PROJECT_COMPLETION_MAP.md")
        self.assertIn("earlier 2026-08-18 completion/integration records remain historical provenance", completion_map)

    def test_readme_binds_fresh_runs_and_current_main(self) -> None:
        text = read("README.md")
        self.assertIn(f"FINAL HUMAN-ACCEPTED CANDIDATE: {ACCEPTED_IMPLEMENTATION}", text)
        self.assertIn(f"FINAL HUMAN-ACCEPTED TREE: {ACCEPTED_TREE}", text)
        self.assertIn(f"FRESH CONSEQUENTIAL RUN: {CONSEQUENTIAL_RUN}", text)
        self.assertIn(f"TRUSTED INDEPENDENT VERIFIER RUN: {TRUSTED_RUN}", text)
        self.assertIn(f"CANONICAL MAIN AT FINAL ACCEPTANCE: {MAIN_AT_ACCEPTANCE}", text)
        self.assertIn("FURTHER MERGE", text)
        self.assertIn("RELEASE", text)
        self.assertIn("DEPLOYMENT", text)
        self.assertIn("TAG", text)

    def test_pre_g18_reconciliation_remains_historical_and_unmodified_in_meaning(self) -> None:
        text = read("evidence/phase-c/P4_RUN94_FINAL_CLOSURE_RECONCILIATION_2026-08-20.md")
        self.assertIn("G-18: OPEN_HUMAN_ONLY", text)
        self.assertIn("PROJECT COMPLETION: BLOCKED ONLY ON G-18", text)
        current = read(NEW_RECORD)
        self.assertIn("pre-G-18", current)
        self.assertIn("G-18: PASS", current)


if __name__ == "__main__":
    unittest.main()
