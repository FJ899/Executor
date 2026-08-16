# P4 Repeatability Policy

Status: Phase-B candidate policy. Not a P4 maturity claim.

## Supported class

The tested P4 class is `BOUNDED_CORRECTNESS_OR_QUALITY_FIX` under the exact GitHub trust profile in `trust_profiles/github-p4-pilots.json`.

For the current completion series:

- target repository must be one of `JTJ07/scriptops` or `JTJ07/creative-os-project-reconstructor`;
- each request pins an exact repository commit and tree;
- each task exposes an observable counterexample before change;
- the effect is limited to the exact allowed production path(s) and frozen patch/file budget;
- required postconditions and regressions are fixed by the direct-human request;
- the worker has no network, secrets or host fallback;
- the only external result is a dedicated branch/commit/draft PR;
- merge, deploy and release remain outside Executor authority.

No result from this series generalizes authority beyond this class or these repositories.

## Global one-shot authority

A human GitHub decision is not made one-shot by a process-local variable or by the pathname of a SQLite database.

The candidate implementation uses two layers:

1. a deterministic GitHub provider ref derived from the authority key as the shared one-shot namespace across runners and local files;
2. SQLite WAL/`BEGIN IMMEDIATE` as the local crash-safe consumption/result ledger.

Changing `run_id`, local ledger path, runner or process must not create a second effect from the same human decision. Provider reservation happens before local effect consumption. Once effect authority has been provider-reserved, failure spends that effect authority fail-closed.

Provider refs under `refs/heads/executor-authority/*` are durable authority receipts. They are evidence, not active implementation branches, and repository cleanup must not delete them.

## Freshness at consequential authority

Freshness is a property of the actual authority reservation, not merely of an earlier request/decision observation or precondition start.

For every decision/effect provider reservation:

- the exact decision expiry is bound into the provider receipt as `not_after`;
- local runtime re-samples UTC after preconditions immediately before effect authorization;
- the GitHub reservation commit is then fetched back and its provider-controlled `committer.date` is compared with `not_after`;
- `provider_created_at >= not_after` is fail-closed: the one-shot provider ref remains spent, local effect consumption does not occur, target mutation does not occur, and review-required success is forbidden;
- a missing or malformed provider reservation timestamp is fail-closed;
- caller-supplied or precondition-start clocks cannot establish freshness for consequential authority.

This provider-time check is the authoritative temporal boundary. The local clock is an early rejection layer, not the sole proof that authority was consumed before expiry.

## Retry policy

Retry is classified by where failure occurs.

### Before effect authority reservation

Examples: image acquisition, exact-source acquisition, request verification, proposal validation, environment validation, or an unobservable precondition.

No target mutation has been authorized. A bounded operator retry may occur while the same verified decision remains fresh, provided no effect authority receipt exists.

### After effect authority reservation

No automatic retry is allowed. The global authority receipt remains spent even if execution later blocks or fails.

A provider reservation created at or after `not_after` is also spent fail-closed: it cannot authorize mutation and cannot be retried with the same decision.

A new consequential attempt requires a new direct-human `ACCEPT` over the then-current exact draft. The new decision receives a new provider event identity and therefore a new authority namespace.

This deliberately prefers an honest `BLOCKED/FAILED` over hidden retry or duplicated effects.

## Failure taxonomy

Every real pilot failure is assigned to one primary class:

- `TRUST_OR_ORIGIN` — request/actor/event/hash/freshness mismatch;
- `DECISION_OR_REPLAY` — invalid, expired, edited or already consumed decision/effect authority;
- `SOLUTION_PROVENANCE` — missing/mismatched External Intelligence provenance or effect-capability violation;
- `INPUT_IDENTITY` — repository/commit/tree mismatch;
- `ENVIRONMENT` — workflow/image/provider identity or unavailable bounded environment;
- `PRECONDITION` — approved counterexample not observed;
- `POSTCONDITION` — target acceptance condition fails after mutation;
- `REGRESSION` — required regression fails or declared discovery executes zero tests;
- `SCOPE` — path/protected-material/patch-budget violation;
- `ISOLATION` — network/secrets/resource/cleanup boundary failure;
- `EVIDENCE` — durable evidence/result binding cannot be completed;
- `HUMAN_REVIEW` — reviewer rejects usefulness/correctness of the draft result.

Attempt-level success and objective-level completion success must be reported separately.

## Solution model/version policy

Every materialized P4 proposal must carry durable provenance with:

- producer role `EXTERNAL_INTELLIGENCE`;
- provider and exact model identifier;
- generation time later than the direct-human request;
- exact request and source identities;
- prompt SHA-256;
- zero human solution edits;
- no effect capability.

A model/provider change does not inherit prior solution evidence. The proposal must be regenerated and its provenance rebound. The resulting pilot must pass the same frozen postconditions/regressions and human review.

A dependency/image change that can affect execution similarly requires a new exact resolved image identity and repeatability evidence. Floating image tags are acquisition locators only; the resolved `sha256:` image identity is the execution identity bound into evidence.

## Regression policy

Exit code zero is necessary but not always sufficient evidence.

For `unittest discover`, Executor also requires a countable `Ran N test(s)` observation with `N > 0`. A silent zero-test run is `BLOCKED`, never aggregate regression PASS.

The human request owns the regression command set. Executor may refuse an insufficient command but may not silently replace it after approval. A corrected regression set therefore requires a new direct-human request/decision event.

## P4 series metrics

The completion series records at minimum:

- distinct authorized task objectives;
- repositories/modules covered;
- objective completion rate;
- first-attempt and retry counts separately;
- failure taxonomy;
- runtime and request-to-consumption latency from durable timestamps;
- human review acceptance rate;
- human review time vs bounded manual estimate;
- incremental new paid-service authorization and whether actual shared platform/provider billing was independently measurable;
- exact model/provenance and exact workflow/image/source identities.

The approved completion map requires multiple real runs across more than one repository or independent module set; it does not prescribe a third task objective. For this bounded completion candidate, the repeatability series is two distinct real objectives across the two authorized repositories, each executed three times under three separate fresh direct-human ACCEPT events (six independently authorized real executions total). Each repetition must start from the same exact pinned source, produce the same bounded patch for its objective, pass the frozen postconditions/regressions, and preserve independent one-shot authority evidence. This is the series presented to Phase C; it does not generalize beyond the supported class or repositories.

## Completion boundary

This policy does not authorize merge, release, deployment, new secrets, new credentials or new paid services.

P4 remains unclaimed until the exact completion candidate passes the approved G-01–G-18 map, independent Phase C, and the final human `EXECUTOR 1.0: ACCEPT` decision. A tag/release exists only if separately authorized.
