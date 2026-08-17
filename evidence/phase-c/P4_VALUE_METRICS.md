# P4 pilot value and repeatability metrics

Status: `EVIDENCE-GATED / NOT A P4 COMPLETION CLAIM`
Date: 2026-08-17

This file defines metric interpretation and preserves durable human observations. It does not claim that the current PR head has passed a fresh consequential P4 series. Exact-head operational values are established by immutable GitHub runs/artifacts/provider receipts and independently verified.

## Source hierarchy

- committed policy/metric semantics: this file + `docs/product/P4_REPEATABILITY_POLICY.md` + `PROJECT_COMPLETION_MAP.md`;
- exact candidate identity: live PR #61 head/tree;
- exact-candidate operational metrics: immutable exact-head GitHub Actions artifacts and provider receipts;
- post-run locator: PR #61 body, which may identify immutable records but cannot redefine metric rules.

A later PR-body statement cannot convert failed/missing exact-head evidence into PASS.

## Historical rejected or superseded completion evidence

The following exact candidates are not current P4 evidence:

- `24107bc8a8186ed1928e098118982efb9d62ffaa` — independent `FALSE-COMPLETION` on global authority/replay;
- `7f662cd487c14d62a4838be8c43cef1358869d50` — independent `BLOCKED` on G-02/G-14;
- `fdf876e0e2af6d9e4ecea2301ecb686a471037bd` — independent `FALSE-COMPLETION` on direct-human/app-mediated GitHub provenance;
- `d11f3dd9d6c484a9c554cd562db46c30e0a333fe` — independent `FALSE-COMPLETION` on effect freshness TOCTOU;
- `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` — a six-execution P4 series DID run and produced raw exact-SHA evidence, but its previous completion verdict was superseded by the later G-04 finding that post-freeze mutable provider state was still being re-read as a retroactive revocation source. Its raw evidence remains historical evidence for `eca7eeb...` only.

Runs, artifacts, provider receipts, review-required results and human ACCEPT events consumed by any rejected/superseded exact candidate remain historical provenance only. They cannot be counted as current exact-candidate consequential success.

`VERDICT superseded != EVIDENCE erased`.

## Direct-human value source

Human actor: `JTJ07` (GitHub user id `219382941`).

Historical bounded value-review source on Executor PR #61:
- comment id: `5308341221`;
- created and updated: `2026-08-16T16:03:33Z`;
- author association: `OWNER`.

The human reported materially less review work than the estimated manual completion path for the two bounded patches below. These observations are retained as historical/bounded human observations; they do not substitute for a fresh exact-candidate consequential series.

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

These are bounded human observations for those reviewed patch heads. They are not a general productivity or ROI claim. A later fresh exact candidate may reference them only as historical endpoint observations unless the independent verifier establishes exactly what remains applicable.

## Approved P4 series definition

The human-approved completion map requires multiple real runs across more than one repository or independent module set. It does **not** prescribe a third distinct task objective.

The bounded series contract is:

- `2` distinct real bounded objectives;
- `2` authorized repositories;
- `3` separately human-authorized executions per objective;
- `6` independently authorized real executions total.

Each new repetition must begin at the same exact pinned source for its objective, produce the same bounded patch, pass the same frozen postconditions/regressions, preserve scope/isolation, and create independent one-shot evidence for **both** `CONTRACT_ACCEPT` and consequential EFFECT authority.

A human ACCEPT already consumed by an earlier exact candidate cannot be reused to make a later candidate's series appear fresh. ACCEPT 001–012 are historical/consumed.

## Revocation-cutoff metrics/evidence

For each future fresh `CONTRACT_ACCEPT`, artifacts must permit independent reconstruction of:

- final live request provider identity/body hash/immutable IDs;
- final live decision provider identity/body hash/immutable IDs;
- exact request and draft binding;
- direct-human provenance and decision edit state;
- final verification timestamp and decision/request freshness evidence;
- immutable authority snapshot SHA-256;
- exact local/global `CONTRACT_ACCEPT` authority key, payload SHA and FINAL result binding;
- `not_after` and provider receipt timing evidence;
- proof that a failed global consumption did not create frozen authority;
- distinction between contract authority and later EFFECT authority.

Post-cutoff source GitHub mutation is not a new metric input for retroactive revocation of an already successfully frozen contract.

## Metrics required from a future fresh exact-candidate consequential series

The independent verifier must derive at least:

- distinct objective count and repository/module coverage;
- completed review-required executions / total executions;
- objective completion rate;
- first-attempt and retry counts separately;
- primary failure taxonomy for any failure/retry;
- per-execution runtime plus aggregate mean/median/total where available;
- request/decision-to-CONTRACT_ACCEPT and effect-reservation latency from durable timestamps where available;
- human review acceptance state and unchanged reviewed target heads;
- human review time versus bounded manual estimate;
- exact model/provider/provenance and prompt hash;
- exact workflow/image/source identities;
- provider-backed CONTRACT_ACCEPT and EFFECT receipt count/state;
- provider freshness evidence for each relevant reservation;
- local SQLite action/result FINAL bindings;
- patch reproducibility within each objective;
- cost disclosure boundary.

No metric is current merely because it existed for `eca7eeb...` or an earlier SHA.

## Failure and retry interpretation

Attempt-level success and objective-level completion are separate.

Before successful `CONTRACT_ACCEPT`, failed final verification or failed global consumption creates no frozen authority. Retry requires a new final live provider verification.

After successful `CONTRACT_ACCEPT` but before EFFECT reservation, bounded operational retry may be allowed by policy without re-reading mutable GitHub issue/comment state as retroactive revocation.

After EFFECT reservation, no automatic consequential retry is allowed. A new consequential attempt requires new direct-human authority.

A provider reservation whose server-controlled timestamp is at/after bound `not_after` is spent fail-closed and may not authorize local effect consumption or mutation.

Failure taxonomy includes trust/origin, contract decision/replay/revocation, solution provenance, input identity, environment, precondition, effect freshness, postcondition, regression, scope, isolation, evidence and human review.

## Cost disclosure

The supported claim is only:

- incremental **new paid-service authorization** for this Phase-B work: `0`.

Not established:

- actual GitHub Actions allocation cost;
- actual OpenAI/model allocation cost;
- actual shared platform/compute cost.

Therefore no document may translate “no new paid service authorized” into “actual cost = 0”.

## Completion interpretation

Even if all future technical/value metrics pass:

- P4 remains unclaimed until fresh independent Phase C passes applicable gates;
- `EXECUTOR 1.0: ACCEPT` remains a separate final human decision;
- merge, release, deploy and tag remain unauthorized unless separately approved.
