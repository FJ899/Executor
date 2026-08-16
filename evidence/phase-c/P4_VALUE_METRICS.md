# P4 pilot value and repeatability metrics

Status: `EVIDENCE-GATED / NOT A P4 COMPLETION CLAIM`
Date: 2026-08-16

This file defines metric interpretation and preserves durable human observations. It does not claim that the current PR head has passed its post-commit workflows. Exact-head operational values are established by immutable GitHub runs/artifacts referenced from PR #61 after those records exist and must be independently verified.

## Source hierarchy

- committed policy/metric semantics: this file + `docs/product/P4_REPEATABILITY_POLICY.md` + `PROJECT_COMPLETION_MAP.md`;
- exact candidate identity: live PR #61 head/tree;
- exact-candidate operational metrics: immutable exact-head GitHub Actions artifacts and provider receipts;
- post-run locator: PR #61 body, which may identify immutable records but cannot redefine these metric rules.

A later PR-body statement cannot convert a failed/missing exact-head run into PASS.

## Historical rejected completion evidence

The following exact candidates are not current P4 evidence:

- `24107bc8a8186ed1928e098118982efb9d62ffaa` — independent `FALSE-COMPLETION` on global authority/replay;
- `7f662cd487c14d62a4838be8c43cef1358869d50` — independent `BLOCKED` on G-02/G-14 despite six corrected executions;
- `fdf876e0e2af6d9e4ecea2301ecb686a471037bd` — independent `FALSE-COMPLETION` on direct-human/app-mediated GitHub provenance;
- `d11f3dd9d6c484a9c554cd562db46c30e0a333fe` — independent `FALSE-COMPLETION` because a decision could expire during a precondition while stale precondition-start time was reused at later effect authorization.

Runs, artifacts, provider receipts, review-required results and human ACCEPT events consumed by any rejected exact candidate remain historical provenance only. They cannot be counted as current exact-candidate success.

## Direct-human value source

Human actor: `JTJ07` (GitHub user id `219382941`).

Authoritative human value-review comment on Executor PR #61:
- comment id: `5308341221`;
- created and updated: `2026-08-16T16:03:33Z`;
- author association: `OWNER`.

The human reported that the Executor-assisted review path required materially less human work than the estimated manual completion path for the two bounded patches below.

## Bounded human-review observations

### ScriptOps PR #8

- target head: `897de878703a029df814f2551b993c3818defa2a`;
- review id: `4946578707`;
- reviewer: `JTJ07` / user id `219382941`;
- review state: `APPROVED`;
- human review time: approximately `3 minutes`;
- human-estimated manual completion time: approximately `15 minutes`.

### Project Reconstructor PR #4

- target head: `e59b9d6c1b496bcb6411e712e7c65cc891578ac3`;
- review id: `4946583370`;
- reviewer: `JTJ07` / user id `219382941`;
- review state: `APPROVED`;
- human review time: approximately `15 seconds`;
- human-estimated manual completion time: approximately `15 minutes`.

These are bounded human observations for these two reviewed patch heads. They are not a general productivity or ROI claim. A fresh exact candidate may rely on these observations only if the independent verifier confirms that the reviewed target heads and patch contents are unchanged and remain the exact outputs under evaluation.

## Approved P4 series definition

The human-approved completion map requires multiple real runs across more than one repository or independent module set. It does **not** prescribe a third distinct task objective.

The bounded completion series frozen by `docs/product/P4_REPEATABILITY_POLICY.md` is:

- `2` distinct real bounded objectives;
- `2` authorized repositories;
- `3` separately human-authorized executions per objective;
- `6` independently authorized real executions total.

Each repetition must begin at the same exact pinned source for its objective, produce the same bounded patch, pass the same frozen postconditions/regressions, preserve scope/isolation, and create independent one-shot global authority evidence.

A human ACCEPT already consumed by an earlier exact candidate cannot be reused to make a later candidate's series appear fresh.

## Metrics required from the current exact-candidate artifacts

For the exact PR #61 head presented to Phase C, the verifier must independently derive at least:

- distinct objective count and repository/module coverage;
- completed review-required executions / total executions;
- objective completion rate;
- first-attempt and retry counts separately;
- primary failure taxonomy for any failure/retry;
- per-execution runtime plus aggregate mean/median/total where available;
- request/decision-to-consumption latency from durable timestamps where available;
- human review acceptance state and unchanged reviewed target heads;
- human review time versus bounded manual estimate;
- exact model/provider/provenance and prompt hash;
- exact workflow/image/source identities;
- provider-backed one-shot authority receipt count/state;
- local SQLite action/result FINAL bindings;
- patch reproducibility within each objective;
- cost disclosure boundary.

No metric is current merely because it existed for an earlier SHA.

## Failure and retry interpretation

Attempt-level success and objective-level completion are separate.

Retries are governed by `docs/product/P4_REPEATABILITY_POLICY.md`:

- before global effect reservation: bounded retry may be allowed while the decision remains fresh and no effect receipt exists;
- after effect reservation: no automatic consequential retry; a new attempt requires a new direct-human ACCEPT.

Failure taxonomy includes trust/origin, decision/freshness/replay, solution provenance, input identity, environment, precondition, postcondition, regression, scope, isolation, evidence and human review.

A freshness failure after preconditions but before effect reservation is a pre-effect BLOCKED attempt; it must never be converted into review-required success and must not consume a consequential effect after expiry.

## Cost disclosure

The supported claim is only:

- incremental **new paid-service authorization** for this Phase-B work: `0`.

Not established:

- actual GitHub Actions allocation cost;
- actual OpenAI/model allocation cost;
- actual shared platform/compute cost.

Therefore no document may translate “no new paid service authorized” into “actual cost = 0”.

## Completion interpretation

A current exact-candidate series can support G-15 only after the immutable exact-head runs/artifacts have been independently checked.

Even if all technical/value metrics pass:

- P4 remains unclaimed until fresh independent Phase C passes the applicable gates;
- `EXECUTOR 1.0: ACCEPT` remains a separate final human decision;
- merge, release, deploy and tag remain unauthorized unless separately approved.
