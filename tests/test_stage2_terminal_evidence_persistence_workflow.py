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
        )
        for token in forbidden:
            with self.subTest(token=token):
                self.assertNotIn(token, self.raw)

    def test_target_repository_is_provenance_only_not_an_effect_destination(self) -> None:
        self.assertIn("'target_repository':'FJ899/executor-pilot-target'", self.raw)
        forbidden_operational_forms = (
            "repository: FJ899/executor-pilot-target",
            "github.com/FJ899/executor-pilot-target.git",
            "git@github.com:FJ899/executor-pilot-target",
            "refs/heads/executor-pilot",
        )
        for token in forbidden_operational_forms:
            with self.subTest(token=token):
                self.assertNotIn(token, self.raw)

    def test_fail_closed_if_discovery_ref_already_exists(self) -> None:
        self.assertIn("git ls-remote --exit-code --heads", self.raw)
        self.assertIn("STAGE2_EVIDENCE_PERSISTENCE_BLOCK", self.raw)
        self.assertNotIn("git push --force", self.raw)
        self.assertNotIn("git push -f", self.raw)

    def test_raw_frozen_source_and_canonical_authority_are_distinct(self) -> None:
        self.assertIn("frozen_result_source_raw.json", self.raw)
        self.assertIn(
            "fdff405f809fa0f55c12ba7c5ca382564cb486e10fbcd2f3911b89107b3d97d7",
            self.raw,
        )
        self.assertIn(
            "16a50e0535a7d9587f1c8751fd22099f61dead107117ad17b904a79a37f8fa8d",
            self.raw,
        )
        self.assertIn("canonical frozen_result hash mismatch", self.raw)
        self.assertIn("source_frozen_result_raw_sha256", self.raw)
        self.assertIn("frozen_result_sha256", self.raw)

    def test_required_source_objects_are_verified_before_persistence(self) -> None:
        required_checks = (
            "AUTHORIZED_AND_FROZEN",
            "SOLUTION_PROVIDED",
            "Stage-2 result carries effect capability",
            "proposal payload hash mismatch",
            "provider evidence ref mismatch",
            "terminal verification manifest Stage-2 result hash mismatch",
            "terminal verification manifest proposal hash mismatch",
            "provider generation binding hash missing",
        )
        for token in required_checks:
            with self.subTest(token=token):
                self.assertIn(token, self.raw)


if __name__ == "__main__":
    unittest.main()
