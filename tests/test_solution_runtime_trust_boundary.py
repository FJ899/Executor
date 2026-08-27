from __future__ import annotations

import unittest
from unittest.mock import patch

from executor.pilot_runtime import PilotBlocked, PilotRuntime
from executor.solution_provider import (
    SolutionProvider,
    VerifiedGenerationEvidence,
)
import tests.test_solution_provider as solution_provider_tests


class SolutionRuntimeTrustBoundaryTests(unittest.TestCase):
    """Adversarial regression for P4 finding #11.

    The exact counterexample is a caller-created verifier populated with a
    caller-created, field-for-field matching VerifiedGenerationEvidence.  It
    must be rejected before provider verification, policy loading, sandbox
    construction, authority reservation, or any effect.
    """

    def test_caller_created_matching_verifier_is_blocked_before_runtime_effect_boundary(self):
        fixture = solution_provider_tests.SolutionProviderTests(
            methodName="test_frozen_contract_to_validated_solution_proposal"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        producer_verifier = solution_provider_tests.FakeGenerationVerifier()
        result = SolutionProvider(
            solution_provider_tests.FakeGenerator(producer_verifier),
            producer_verifier,
        ).provide(
            frozen_result=fixture.frozen,
            checkout_root=fixture.repo,
        )

        observed = producer_verifier.records[result.generation_evidence_ref]
        caller_created = VerifiedGenerationEvidence(
            evidence_ref=observed.evidence_ref,
            provider=observed.provider,
            model=observed.model,
            generated_at=observed.generated_at,
            frozen_contract_sha256=observed.frozen_contract_sha256,
            repository=observed.repository,
            commit=observed.commit,
            tree=observed.tree,
            context_sha256=observed.context_sha256,
            prompt_sha256=observed.prompt_sha256,
            response_sha256=observed.response_sha256,
            generation_challenge_sha256=observed.generation_challenge_sha256,
            generation_challenge_issued_at=observed.generation_challenge_issued_at,
            freeze_receipt_sha256=observed.freeze_receipt_sha256,
            verification_method=observed.verification_method,
        )
        attacker_verifier = solution_provider_tests.FakeGenerationVerifier()
        attacker_verifier.records[result.generation_evidence_ref] = caller_created

        with patch("executor.pilot_runtime.load_execution_policy_snapshot") as load_policy:
            with self.assertRaisesRegex(
                PilotBlocked,
                "caller-supplied solution-generation verifier is forbidden",
            ):
                PilotRuntime(
                    **fixture._runtime_kwargs(result.proposal),
                    generation_verifier=attacker_verifier,
                )

        self.assertEqual(attacker_verifier.calls, [])
        load_policy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
