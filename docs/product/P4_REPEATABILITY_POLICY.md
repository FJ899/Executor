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

Changing `run_id`, local ledger path, runner or process must not create a second legal consumption from the same human authority. Provider reservation happens before local consumption. Once an authority has been provider-reserved, ambiguous failure is fail-closed and the provider namespace is not silently reusable.

Provider refs under `refs/heads/executor-authority/*` are durable authority receipts. They are evidence, not active implementation branches, and repository cleanup must not delete them.

## CONTRACT_ACCEPT revocation cutoff

Human-approved semantics are recorded verbatim in `PHASE_B_AUTHORIZATION.md`:

`AKCEPTUJĘ FINAL LIVE VERIFICATION AS REVOCATION CUTOFF BOUND INTO SUCCESSFUL GLOBAL CONTRACT_ACCEPT CONSUMPTION`.

`CONTRACT_ACCEPT` formation and consequential `EFFECT` authorization are separate authority consumptions.

For `CONTRACT_ACCEPT`:

1. The GitHub request and ACCEPT remain revocable before the cutoff.
2. Immediately before global `CONTRACT_ACCEPT` consumption, Executor performs a final live re-fetch through the existing authoritative `verify_github_request(...)` and `verify_github_decision(...)` functions.
3. The exact final verified request/decision provider evidence is materialized into an immutable authority snapshot. Its SHA-256, not only the decision body hash, is the payload bound to global `CONTRACT_ACCEPT` consumption.
4. The snapshot includes the exact request and decision provider identities, body hashes and parsed payloads, immutable issue/comment IDs, direct-human provenance, request/draft binding, decision edit state, verification/freshness evidence and pinned target commit/tree evidence.
5. If final live verification succeeds but global consumption fails, no frozen authority exists. The failed verification snapshot is not cached authority. A retry must perform a new final live provider verification.
6. If exact snapshot consumption and result binding succeed, the resulting `AUTHORIZED_AND_FROZEN` contract embeds that snapshot and its successful local/global `CONTRACT_ACCEPT` receipt binding.
7. After that successful cutoff, later edit/deletion of the source request or ACCEPT does not retroactively revoke or alter the frozen contract. Post-cutoff provider mutation is historical mutation of the source event.
8. Execution from the frozen contract validates the immutable snapshot and successful `CONTRACT_ACCEPT` receipt. It does not re-fetch mutable request/comment state as a retroactive revocation source.

GitHub is not claimed to provide an atomic transaction spanning Issue/Comment state and Git refs. The system guarantee is the explicitly accepted linearization semantics above.

## Freshness at consequential authority

Freshness is a property of the actual authority reservation, not merely of an earlier request/decision observation or precondition start.

For `CONTRACT_ACCEPT`, the final live verification must observe a fresh decision, and the exact decision expiry is bound into the global receipt as `not_after`. A provider reservation at/after expiry is fail-closed and cannot create executable frozen authority.

For every consequential EFFECT reservation:

- the frozen decision expiry is bound into the provider receipt as `not_after`;
- local runtime re-samples UTC after preconditions immediately before effect authorization;
- the GitHub reservation commit is then fetched back and its provider-controlled `committer.date` is compared with `not_after`;
- `provider_created_at >= not_after` is fail-closed: the one-shot provider ref remains spent, local effect consumption does not occur, target mutation does not occur, and review-required success is forbidden;
- a missing or malformed provider reservation timestamp is fail-closed;
- caller-supplied or precondition-start clocks cannot establish freshness for consequential authority.

This provider-time check is the authoritative temporal boundary for EFFECT authority. The local clock is an early rejection layer, not the sole proof that effect authority was consumed before expiry.

## Retry policy

Retry is classified by where failure occurs.

### Before successful CONTRACT_ACCEPT

A failed final live verification creates no authority. A failed global `CONTRACT_ACCEPT` consumption creates no frozen authority. Any retry must perform a fresh final live provider verification; a previously verified snapshot cannot become dormant authority later.

If a global provider reservation may have succeeded but the outcome is ambiguous, the one-shot namespace is treated as spent/fail-closed. Executor does not manufacture a replacement authority from the same event.

### Before EFFECT authority reservation

Examples after a valid freeze: image acquisition, exact-source acquisition, proposal validation, environment validation, or an unobservable precondition.

No target mutation has been authorized. A bounded operator retry may occur while the frozen authority remains valid and provided no effect authority receipt exists. Post-cutoff mutable GitHub request/comment state is not a revocation input for that already frozen authority.

### After EFFECT authority reservation

No automatic consequential retry is allowed. The global effect authority receipt remains spent even if execution later blocks or fails.

A provider reservation created at or after `not_after` is also spent fail-closed: it cannot authorize mutation and cannot be retried with the same effect authority.

A new consequential attempt requires a new direct-human `ACCEPT` over the then-current exact draft. The new decision receives a new provider event identity and therefore a new `CONTRACT_ACCEPT` namespace and, after freeze, a new effect namespace.

This deliberately prefers an honest `BLOCKED/FAILED` over hidden retry or duplicated effects.

## Failure taxonomy

Every real pilot failure is assigned to one primary class:

- `TRUST_OR_ORIGIN` — request/actor/event/hash/final-live verification mismatch;
- `DECISION_OR_REPLAY` — invalid, expired, edited, revoked pre-cutoff, substituted or already consumed contract/effect authority;
- `SOLUTION_PROVENANCE` — missing/mismatched External Intelligence provenance or effect-capability violation;
- `INPUT_IDENTITY` — repository/commit/tree mismatch;
- `ENVIRONMENT` — workflow/image/provider identity or unavailable bounded environment;
- `PRECONDITION` — approved counterexample not observed;
- `POSTCONDITION` — target acceptance condition fails after mutation;
- `REGRESSION` — required regression fails or declared discovery executes zero tests;
- `SCOPE` — path/protected-material/patch-budget violation;
- `ISOLATION` — network/secrets/resource/cleanup boundary failure;
- `EVIDENCE` — durable snapshot/receipt/result binding cannot be completed;
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
- exact model/provenance and exact workflow/image/source identities;
- exact `CONTRACT_ACCEPT` snapshot hashes and successful receipt bindings separately from EFFECT receipts.

The approved completion map requires multiple real runs across more than one repository or independent module set; it does not prescribe a third task objective. The bounded proof contract remains two distinct real objectives across the two authorized repositories, each executed three times under three separate fresh direct-human ACCEPT events (six independently authorized real executions total).

The six-run series previously executed for exact head `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` remains historical evidence for that SHA only. Its previous completion verdict was superseded by the later G-04 revocation-cutoff finding. Its consumed ACCEPT events must not satisfy a new candidate. A new exact candidate requires a completely fresh consequential six-execution series after fresh human authority is supplied.

## Completion boundary

This policy does not authorize merge, release, deployment, new secrets, new credentials or new paid services.

P4 remains unclaimed until the exact completion candidate passes the approved G-01–G-18 map, fresh consequential proof, independent Phase C, and the final human `EXECUTOR 1.0: ACCEPT` decision. A tag/release exists only if separately authorized.
