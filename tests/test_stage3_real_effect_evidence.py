from __future__ import annotations

import json
import os
import platform
import unittest
from pathlib import Path

from executor.github_trust import canonical_json
from executor.stage3_runtime import (
    CONTROL_PLANE,
    EVIDENCE_BUNDLE_OUTPUT,
    REPOSITORY_PLANE,
    Stage3MutationRuntime,
    Stage3TerminalStatus,
)


class Stage3RealEffectEvidenceTests(unittest.TestCase):
    def test_frozen_trust_profile_is_canonical_closed_and_bound_to_exact_producer(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy_path = root / "trust_profiles/stage3_generation_identity_policy.json"
        trust_path = root / "trust_profiles/stage3_generation_attestation_root.jsonl"
        self.assertTrue(policy_path.is_file())
        self.assertTrue(trust_path.is_file())
        policy_raw = policy_path.read_bytes()
        policy = json.loads(policy_raw)
        self.assertEqual(policy_raw, canonical_json(policy).encode("utf-8"))
        self.assertEqual(
            set(policy),
            {
                "schema_version",
                "oidc_issuer",
                "repository",
                "signer_reusable_workflow",
                "signer_digest",
                "accepted_predicate_type",
                "accepted_evidence_schema",
                "verification_method",
                "trusted_root_sha256",
            },
        )
        self.assertEqual(policy["oidc_issuer"], "https://token.actions.githubusercontent.com")
        self.assertEqual(policy["repository"], "FJ899/Executor")
        self.assertEqual(
            policy["signer_reusable_workflow"],
            ".github/workflows/stage3-generation-verifier-attestation.yml",
        )
        self.assertEqual(
            policy["signer_digest"],
            "52cb6465fe9ab59b6ffd259801bda521e9155294",
        )
        self.assertEqual(
            policy["accepted_predicate_type"],
            "https://fj899.github.io/Executor/attestations/provider-generation-evidence/v1",
        )
        self.assertEqual(
            policy["accepted_evidence_schema"],
            "executor-provider-generation-evidence/1.0",
        )
        self.assertEqual(policy["verification_method"], "OPENAI_RESPONSES_RETRIEVE_V1")
        self.assertEqual(
            policy["trusted_root_sha256"],
            "3c2cc7f357dc064ec527fdcd78da6e9245c21a381e1abaa0f2b62b186bcac1a1",
        )
        lines = trust_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(lines)
        for line in lines:
            self.assertIsInstance(json.loads(line), dict)

    def test_real_provider_sigstore_human_authority_observable_effect_evidence(self) -> None:
        if os.environ.get("STAGE3_REQUIRE_REAL_EFFECT_EVIDENCE") != "1":
            self.skipTest(
                "NOT YET P4 AUDITED: P4 must enable STAGE3_REQUIRE_REAL_EFFECT_EVIDENCE=1 for the mandatory real effect run"
            )
        self.assertEqual(platform.system(), "Linux")
        self.assertIn(platform.machine(), {"x86_64", "AMD64"})
        self.assertEqual(REPOSITORY_PLANE, Path("/workspace/repo"))
        self.assertEqual(CONTROL_PLANE, Path("/workspace/.stage3-control"))

        result = Stage3MutationRuntime().execute()
        self.assertIs(result.terminal_status, Stage3TerminalStatus.MUTATION_APPLIED_REVIEW_REQUIRED)
        self.assertIs(result.authority_consumed, True)
        self.assertEqual(result.repository_write_count_claim, 1)
        self.assertTrue(EVIDENCE_BUNDLE_OUTPUT.is_file())
        evidence = json.loads(EVIDENCE_BUNDLE_OUTPUT.read_text(encoding="utf-8"))
        effect = evidence["effect_and_post_state"]
        self.assertEqual(effect["changed_paths"], [effect["mutation_path"]])
        self.assertEqual(effect["terminal_status"], "MUTATION_APPLIED_REVIEW_REQUIRED")
        self.assertIs(effect["control_inputs_unchanged"], True)
        self.assertEqual(effect["host_observer"]["network_effect_count"], 0)
        self.assertEqual(effect["host_observer"]["secret_exposure_count"], 0)
        self.assertEqual(effect["host_observer"]["post_worker_exec_count"], 0)
        self.assertEqual(effect["host_observer"]["git_publication_effect_count"], 0)
        self.assertEqual(effect["host_observer"]["task_command_exec_count"], 0)
        self.assertEqual(
            evidence["environment_and_source"]["pre_git_identities"],
            effect["post_git_identities"],
        )

        replay = Stage3MutationRuntime().execute()
        self.assertIs(replay.terminal_status, Stage3TerminalStatus.BLOCK)
        self.assertIs(replay.authority_consumed, False)
        self.assertEqual(replay.repository_write_count_claim, 0)


if __name__ == "__main__":
    unittest.main()
