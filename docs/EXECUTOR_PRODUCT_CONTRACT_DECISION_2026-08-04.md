# Executor Product Contract v1.0 — decision record

Date: 2026-08-04

## User decision

The user explicitly approved the narrow Executor product direction:

```text
complete repository task contract
-> controlled analysis and change
-> repository and regression tests
-> independently sealed evidence
-> draft PR
-> ACTION_COMPLETED_REVIEW_REQUIRED / BLOCKED / FAILED
-> human review and decision outside Executor
```

## Product consequence

- P3 remains the first real-value MVP.
- Company Loop, Ginseng, multi-agent execution, auto merge, multi-repository execution, UI and full autonomy remain outside P3.
- Every proposed function must identify the current P1/P2/P3 blocker it removes.
- Missing required input or missing independent evidence fails closed as `BLOCKED`.
- Executor cannot self-accept or merge its result.

## Implementation claim

```text
PRODUCT CONTRACT: DOCUMENTED
RUNTIME ENFORCEMENT: NOT CLAIMED
P1: NOT ACCEPTED
P2: NOT IMPLEMENTED
P3 PILOT CONTRACT-001: NOT SELECTED
```

This record is decision evidence only. It is not runtime evidence and does not advance the current product level.
