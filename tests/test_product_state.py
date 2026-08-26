from __future__ import annotations

import unittest

from executor.product_state import (
    ACTIVE_STATE_ENGINE,
    RUNSTORE_ROLE,
    HumanAcceptance,
    ProductStateError,
    ReviewState,
    TechnicalResult,
    mark_draft_pr_created,
    record_human_acceptance,
    state_from_pilot_status,
)


class ProductStateTests(unittest.TestCase):
    def test_active_runtime_is_explicit_and_runstore_is_legacy(self) -> None:
        self.assertEqual(ACTIVE_STATE_ENGINE, "PilotRuntime")
        self.assertEqual(RUNSTORE_ROLE, "LEGACY_GENERIC_COMPATIBILITY_ONLY")

    def test_success_is_not_called_pass_and_requires_review(self) -> None:
        state = state_from_pilot_status("ACTION_COMPLETED_REVIEW_REQUIRED")
        self.assertEqual(state.technical_result, TechnicalResult.SUCCEEDED)
        self.assertEqual(state.review, ReviewState.REQUIRED)
        self.assertEqual(state.human_acceptance, HumanAcceptance.PENDING)
        self.assertNotIn("PASS", state.to_dict().values())

    def test_draft_pr_creation_does_not_equal_human_acceptance(self) -> None:
        state = mark_draft_pr_created(
            state_from_pilot_status("ACTION_COMPLETED_REVIEW_REQUIRED")
        )
        self.assertEqual(state.consequential_effect, "DRAFT_PR_CREATED_AND_OBSERVED")
        self.assertEqual(state.review, ReviewState.REQUIRED)
        self.assertEqual(state.human_acceptance, HumanAcceptance.PENDING)

        accepted = record_human_acceptance(state, accepted=True)
        self.assertEqual(accepted.review, ReviewState.COMPLETED)
        self.assertEqual(accepted.human_acceptance, HumanAcceptance.ACCEPTED)

    def test_failed_or_blocked_run_cannot_be_promoted_to_draft_pr(self) -> None:
        for status in ("FAILED", "BLOCKED", "STALE"):
            with self.subTest(status=status), self.assertRaises(ProductStateError):
                mark_draft_pr_created(state_from_pilot_status(status))


if __name__ == "__main__":
    unittest.main()
