# P4 pilot value metrics

Status: HISTORICAL VALUE EVIDENCE + CORRECTED SERIES PENDING / NOT A P4 COMPLETION CLAIM
Date: 2026-08-16

This file preserves direct-human value observations from the first two pilot outputs while making explicit that their Executor completion candidate was rejected by independent Phase C. It does not authorize merge, deployment, release, or a maturity claim.

## Independent Phase-C correction

Historical Executor candidate `24107bc8a8186ed1928e098118982efb9d62ffaa` was rejected as `FALSE-COMPLETION` because human effect authority was replayable. Additional evidence gaps were also identified.

Therefore:

- the reviews below remain valid observations about the two target patches;
- the old exact-candidate artifacts do **not** count as corrected P4 authority/replay proof;
- no success-rate metric below may present the rejected candidate as P4 PASS;
- a new corrected real-pilot series is required.

## Direct-human source

Human actor: `JTJ07` (GitHub user id `219382941`)

Authoritative value-review comment on Executor PR #61:
- comment id: `5308341221`
- created: `2026-08-16T16:03:33Z`
- updated: `2026-08-16T16:03:33Z`
- author association: `OWNER`

The human recorded that the Executor-assisted path required materially less human work than manual completion for these two reviewed patches.

## Historical patch-review observations

### ScriptOps PR #8

- target head: `897de878703a029df814f2551b993c3818defa2a`
- review id: `4946578707`
- reviewer: `JTJ07` / user id `219382941`
- review state: `APPROVED`
- human review time: approximately `3 minutes`
- human-estimated manual completion time: approximately `15 minutes`
- bounded ratio from the estimates: about `5x` less review time

### Project Reconstructor PR #4

- target head: `e59b9d6c1b496bcb6411e712e7c65cc891578ac3`
- review id: `4946583370`
- reviewer: `JTJ07` / user id `219382941`
- review state: `APPROVED`
- human review time: approximately `15 seconds`
- human-estimated manual completion time: approximately `15 minutes`
- bounded ratio from the estimates: about `60x` less review time

Both PRs remain intentionally DRAFT and unmerged.

## Historical objective observations

- patch outputs reviewed: `2/2`;
- patch reviews approved: `2/2`;
- these are **review acceptance observations**, not a corrected P4 objective-completion rate;
- the old Reconstructor evidence included a declared unittest discovery that ran zero tests, so its old aggregate regression PASS is not accepted as corrected evidence.

## Corrected P4 series requirements

`docs/product/P4_REPEATABILITY_POLICY.md` freezes the candidate measurement policy.

Before a P4 claim is presented again, evidence must cover at least three distinct real bounded task objectives across the two authorized repositories or independent modules, including:

- corrected global one-shot authority proof;
- fresh exact request/decision evidence;
- exact workflow/image/source identity;
- post-request External Intelligence provenance;
- real postconditions and non-empty declared regression evidence;
- objective completion rate and first-attempt/retry counts reported separately;
- failure taxonomy;
- runtime and request-to-consumption latency;
- human review acceptance/time evidence;
- model/dependency identity and stability evidence;
- bounded cost disclosure.

## Cost disclosure

- new paid services authorized for this Phase B work: none;
- actual shared platform/provider allocation or billing cost: **not independently measured**;
- this file must not translate “no new paid service authorized” into a claim of zero actual compute/platform cost.

## Interpretation boundary

The historical reviews support only this statement:

> For two bounded patches, the human reported materially less review effort than the human estimated for manual completion.

They do not establish general productivity, ROI, corrected P4 success rate, P4 acceptance, or product completion.
