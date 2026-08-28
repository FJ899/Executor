from __future__ import annotations

import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "stage2-terminal-evidence-persistence.yml"


class Stage2TerminalEvidencePersistenceWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_is_reusable_only_and_has_no_direct_execution_trigger(self) -> None:
        self.assertIn("workflow_call:", self.raw)
        self.assertNotIn("workflow_dispatch:", self.raw)
        self.assertNotIn("\n  push:\n", self.raw)
        self.assertNotIn("\n  pull_request:\n", self.raw)

    def test_persists_only_under_stage2_evidence_namespace(self) -> None:
        self.assertIn('branch="evidence/stage2/${chain_id}"', self.raw)
        self.assertIn('prefix="evidence/stage2/${chain_id}"', self.raw)
        self.assertIn('HEAD:refs/heads/${branch}', self.raw)
        self.assertIn("frozen_result.json", self.raw)
        self.assertIn("stage2_result.json", self.raw)
        self.assertIn("validated_solution_proposal.json", self.raw)
        self.assertIn("manifest.json", self.raw)

    def test_does_not_call_provider_or_stage3_effect(self) -> None:
        forbidden = (
            "OPENAI_API_KEY",
            "openai_read_credential",
            "api.openai.com",
            "Stage3MutationRuntime",
            "human-stage3-effect-authorization",
            "FJ899/executor-pilot-target",
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, self.raw)

    def test_fail_closed_if_discovery_ref_already_exists(self) -> None:
        self.assertIn("git ls-remote --exit-code --heads", self.raw)
        self.assertIn("STAGE2_EVIDENCE_PERSISTENCE_BLOCK", self.raw)
        self.assertNotIn("git push --force", self.raw)
        self.assertNotIn("git push -f", self.raw)

    def test_required_source_objects_are_verified_before_persistence(self) -> None:
        required_checks = (
            "AUTHORIZED_AND_FROZEN",
            "SOLUTION_PROVIDED",
            "Stage-2 result carries effect capability",
            "proposal payload hash mismatch",
            "provider evidence ref mismatch",
            "terminal manifest Stage-2 result hash mismatch",
            "terminal manifest proposal hash mismatch",
        )
        for token in required_checks:
            with self.subTest(token=token):
                self.assertIn(token, self.raw)


if __name__ == "__main__":
    unittest.main()
