from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "evidence/phase-c/P4_RUN94_FINAL_CLOSURE_RECONCILIATION_2026-08-20.md"


class P4Run94FinalClosureReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = RECORD.read_text(encoding="utf-8")

    def test_exact_current_identities_are_bound(self) -> None:
        for token in (
            "3cd0c8d747fef06f82c01cdab8449c7c8a100038",
            "c739aaa989a15eaed65996d7a0b5242a0ec26d7e",
            "32404181188",
            "32407901358",
            "e73f1d410e663c85f7552ac92a492ef45d6a2901",
            "74d4b9f7e4acaa5bfb670cfe089bc087bf95a285b56552f88507cda4e5785cf6",
            "050358461cbebe1cb11a1611635243a255440aad582310493cf5034eaec15568",
            "a567849bcbe686abcdb4511b091e6ae55d227fdf",
            "03ec27d3015b5c086a5dc6db7dc558208fe2a478",
            "96af1f1c4ace80ca821bb0aaeb17899c6c1039dd",
        ):
            self.assertIn(token, self.text)

    def test_recomputed_gates_are_pass_without_g18(self) -> None:
        for token in (
            "G-02: PASS",
            "G-13: PASS",
            "G-15: PASS",
            "G-16: PASS",
            "G-17: PASS",
            "G-18: OPEN_HUMAN_ONLY",
            "PROJECT COMPLETION: BLOCKED ONLY ON G-18",
        ):
            self.assertIn(token, self.text)

    def test_post_merge_status_removes_stale_pre_merge_wording(self) -> None:
        for stale in (
            'version: "1.0-candidate"',
            'status: "NON-CANONICAL CANDIDATE / G-18 OPEN"',
            'claim_reconciliation_authority: "CANDIDATE_ONLY"',
            "G-02: CANDIDATE_READY_NOT_CANONICAL",
            "G-02: CANDIDATE READY / NOT CANONICAL",
            "CLAIM RECONCILIATION: CANDIDATE ONLY / NOT MERGED",
            "This candidate exists to remove stale finish-line wording",
        ):
            self.assertNotIn(stale, self.text)
        self.assertIn('status: "G-02 PASS / G-18 OPEN"', self.text)
        self.assertIn(
            'claim_reconciliation_authority: "CANONICALIZED_BY_AUTHORIZED_MERGE_PR_77"',
            self.text,
        )
        self.assertIn("CLAIM RECONCILIATION: CANONICALIZED BY AUTHORIZED MERGE PR #77", self.text)

    def test_status_correction_does_not_create_final_acceptance(self) -> None:
        self.assertIn('g18_authority: "NONE"', self.text)
        self.assertIn('merge_authority: "NONE"', self.text)
        self.assertIn('release_authority: "NONE"', self.text)
        self.assertIn('deploy_authority: "NONE"', self.text)
        self.assertIn('tag_authority: "NONE"', self.text)
        self.assertIn("EXECUTOR 1.0 FINAL ACCEPTANCE FOR 3cd0c8d...: NOT YET CREATED", self.text)

    def test_historical_g18_is_not_transferred(self) -> None:
        self.assertIn("f60829f90ea2f69dc501582daf109b59676be07e", self.text)
        self.assertIn("neither revokes it nor silently transfers it", self.text)


if __name__ == "__main__":
    unittest.main()
