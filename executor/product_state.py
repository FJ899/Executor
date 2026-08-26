from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


ACTIVE_STATE_ENGINE = "PilotRuntime"
RUNSTORE_ROLE = "LEGACY_GENERIC_COMPATIBILITY_ONLY"


class ProductStateError(ValueError):
    pass


class TechnicalExecution(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    COMPLETED = "COMPLETED"


class TechnicalResult(StrEnum):
    UNKNOWN = "UNKNOWN"
    SUCCEEDED = "SUCCEEDED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    STALE = "STALE"


class ReviewState(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    COMPLETED = "COMPLETED"


class HumanAcceptance(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class CanonicalProductState:
    technical_execution: TechnicalExecution
    technical_result: TechnicalResult
    review: ReviewState
    human_acceptance: HumanAcceptance
    consequential_effect: str

    def to_dict(self) -> dict[str, Any]:
        return {key: value.value if isinstance(value, StrEnum) else value for key, value in asdict(self).items()}


def state_from_pilot_status(status: str) -> CanonicalProductState:
    """Normalize active PilotRuntime status without introducing a synthetic PASS."""

    if status == "ACTION_COMPLETED_REVIEW_REQUIRED":
        return CanonicalProductState(
            technical_execution=TechnicalExecution.COMPLETED,
            technical_result=TechnicalResult.SUCCEEDED,
            review=ReviewState.REQUIRED,
            human_acceptance=HumanAcceptance.PENDING,
            consequential_effect="NOT_YET_CREATED",
        )
    if status == "BLOCKED":
        return CanonicalProductState(
            technical_execution=TechnicalExecution.COMPLETED,
            technical_result=TechnicalResult.BLOCKED,
            review=ReviewState.NOT_REQUIRED,
            human_acceptance=HumanAcceptance.NOT_APPLICABLE,
            consequential_effect="NOT_CREATED",
        )
    if status == "FAILED":
        return CanonicalProductState(
            technical_execution=TechnicalExecution.COMPLETED,
            technical_result=TechnicalResult.FAILED,
            review=ReviewState.NOT_REQUIRED,
            human_acceptance=HumanAcceptance.NOT_APPLICABLE,
            consequential_effect="NOT_CREATED_OR_RECOVERY_REQUIRED",
        )
    if status == "STALE":
        return CanonicalProductState(
            technical_execution=TechnicalExecution.NOT_STARTED,
            technical_result=TechnicalResult.STALE,
            review=ReviewState.NOT_REQUIRED,
            human_acceptance=HumanAcceptance.NOT_APPLICABLE,
            consequential_effect="NOT_CREATED",
        )
    raise ProductStateError(f"unsupported active pilot status: {status!r}")


def mark_draft_pr_created(state: CanonicalProductState) -> CanonicalProductState:
    if (
        state.technical_result is not TechnicalResult.SUCCEEDED
        or state.review is not ReviewState.REQUIRED
        or state.human_acceptance is not HumanAcceptance.PENDING
    ):
        raise ProductStateError("draft PR effect requires successful execution awaiting review")
    return CanonicalProductState(
        technical_execution=state.technical_execution,
        technical_result=state.technical_result,
        review=state.review,
        human_acceptance=state.human_acceptance,
        consequential_effect="DRAFT_PR_CREATED_AND_OBSERVED",
    )


def record_human_acceptance(
    state: CanonicalProductState,
    *,
    accepted: bool,
) -> CanonicalProductState:
    if state.review is not ReviewState.REQUIRED:
        raise ProductStateError("human acceptance requires a review-required result")
    return CanonicalProductState(
        technical_execution=state.technical_execution,
        technical_result=state.technical_result,
        review=ReviewState.COMPLETED,
        human_acceptance=(HumanAcceptance.ACCEPTED if accepted else HumanAcceptance.REJECTED),
        consequential_effect=state.consequential_effect,
    )
