# Independent Phase C Handoff

## Status model

`CORRECTIVE REWORK / FRESH HUMAN AUTHORITY REQUIRED / P4 NOT CLAIMED`

This committed document deliberately does **not** encode a transient post-commit workflow state such as `EXECUTION PENDING` or `READY`.

Reason: every exact-candidate proof workflow runs only after the candidate commit exists. Writing the run IDs or post-run verdict back into this file would create a new commit and invalidate the exact SHA that was actually tested.

Canonical source hierarchy for Phase C is therefore:

1. the current `JTJ07/Executor#61` head commit and tree define the candidate implementation and policy;
2. this committed handoff defines the evidence contract and completion rules;
3. immutable GitHub Actions runs, artifacts, provider authority receipts, issues/comments and target reviews establish post-commit facts for that exact SHA;
4. PR #61 body may contain **locators only** for those immutable post-commit records and may not override committed policy or requirements;
5. the independent verifier must resolve every locator itself and fail closed on any mismatch.

A mutable PR-body statement is never sufficient evidence by itself.

## Human-selected constants

- DONE: P4 Repeatable Executor 1.0.
- Trusted front door/provider: external GitHub intake.
- Allowed human actor/profile: `trust_profiles/github-p4-pilots.json`.
- Solution ownership: External Intelligence without effect authority.
- Pilot repositories: `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`.
- Supported class: `BOUNDED_CORRECTNESS_OR_QUALITY_FIX` within the frozen profile limits.
- External effects: dedicated branch, commit and draft PR only.
- Forbidden without separate authorization: merge, deploy, release, tag, new secrets, new credentials and new paid services.

## Historical rejected candidates

Independent Phase C has rejected multiple exact candidates. All associated runs, artifacts, provider receipts and consumed human decisions are historical evidence only and may not satisfy a later exact-candidate gate.

- `24107bc8a8186ed1928e098118982efb9d62ffaa` — `FALSE-COMPLETION`: global authority/replay boundary was insufficient.
- `7f662cd487c14d62a4838be8c43cef1358869d50` — `BLOCKED`: G-02 canonical truth and G-14 exact-head CI binding.
- `fdf876e0e2af6d9e4ecea2301ecb686a471037bd` — `FALSE-COMPLETION`: app-mediated GitHub events were not fail-closed as non-human.
- `d11f3dd9d6c484a9c554cd562db46c30e0a333fe` — `FALSE-COMPLETION`: decision freshness TOCTOU. `PilotRuntime.execute()` sampled time before preconditions and the later effect authorization reused that stale time, so a decision could expire during a legal precondition and still authorize the first consequential effect.

The rejected failure classes are mandatory regression targets:

1. same human decision + different caller `run_id` must not mint a second effect;
2. same human decision + different local SQLite file/runner must not mint a second global authority namespace;
3. External Intelligence provenance must be post-request, exact-bound and authority-free;
4. workflow and resolved image identity must be bound into execution evidence;
5. `unittest discover` reporting zero tests must fail closed;
6. P4 repeatability evidence must match the approved map and policy;
7. canonical state must not contradict live exact-candidate evidence;
8. request and decision direct-human provenance must fail closed on app-mediated or provider-unverifiable events;
9. decision freshness must be evaluated after preconditions at the effect-authorization boundary, and a decision that expires during a precondition must block before AAP/effect reservation, mutation or review-required success reporting;
10. the GitHub provider reservation itself must prove freshness using its server-controlled reservation commit timestamp against the exact decision `not_after` deadline.

Concrete human ACCEPT events consumed by any rejected exact candidate remain provenance only and must not be reused.

## Corrective architecture to verify

The candidate architecture must implement and independently prove:

- deterministic GitHub provider-backed authority receipt refs as the global one-shot uniqueness boundary;
- stable decision/effect identities independent of caller-controlled `run_id` and local ledger path;
- local SQLite WAL / `BEGIN IMMEDIATE` as crash-safe evidence and result binding, not as the sole global uniqueness root;
- exact GitHub Actions workflow identity and resolved Docker image identity in action/result evidence;
- post-request External Intelligence provenance with model/provider/prompt hash, zero human solution edits and no effect capability;
- fail-closed zero-test discovery handling;
- bounded retry/failure/model/dependency policy in `docs/product/P4_REPEATABILITY_POLICY.md`;
- provider-verifiable direct-human request and decision origin with `performed_via_github_app` present and exactly `null`;
- a real UTC freshness sample at effect authorization after preconditions, with no caller-supplied or precondition-start authority clock;
- the exact decision expiry bound into each GitHub authority receipt as `not_after`, followed by a read-back of the reservation commit whose provider-controlled `committer.date` must be strictly earlier than `not_after`; missing/malformed timestamps or `provider_created_at >= not_after` are fail-closed and may spend the one-shot ref but may not permit local effect consumption or target mutation.

## Corrected series contract

The human-approved completion map requires multiple real runs across more than one repository or independent module set. It does not require a third distinct task objective.

For this bounded candidate the committed series contract is:

- ScriptOps objective from issue #65;
- Project Reconstructor objective from issue #64;
- two distinct real objectives across the two authorized repositories;
- three separate fresh direct-human ACCEPT events per objective;
- six independently authorized real executions total;
- every repetition starts from the same exact pinned source for that objective;
- every repetition must produce the same bounded patch, pass frozen postconditions/regressions, preserve scope/isolation, and produce independent one-shot authority evidence.

Human ACCEPT events consumed by an earlier exact candidate are historical and cannot be silently reused for a later candidate.

## Post-commit exact-candidate evidence contract

A fresh Phase C may report technical PASS only if it independently confirms, for the current PR #61 head SHA/tree:

- foundation CI checked out and asserted the **exact PR head SHA**, not `refs/pull/*/merge`;
- GP001 replay is green on the exact head;
- the corrected real-pilot series is green on the exact head;
- the six human decision events used by that exact series are new direct `JTJ07` owner comments, unedited, fresh at consumption, exact-bound and each consumed at most once;
- request and decision provider evidence has `performed_via_github_app` present and exactly `null`;
- a dedicated adversarial regression proves that a decision which expires during a precondition is BLOCKED before effect authority and cannot produce `ACTION_COMPLETED_REVIEW_REQUIRED`;
- provider-time regressions prove that a reservation commit at/after `not_after` fails closed, leaves the one-shot ref spent, and cannot enable local effect consumption or mutation;
- successful exact-series provider receipts expose both `not_after` and `provider_created_at`, with provider time strictly before expiry;
- the runtime public/effect-authorization interfaces expose no caller-supplied authority clock capable of recreating the stale-time path;
- both pilot artifacts contain raw run reports, identical per-objective patches, exact source/head/tree/workflow/image identities and the local SQLite ledgers;
- provider-backed decision/effect receipt refs exist live and their FINAL commits match artifact/local result bindings;
- same-run, cross-run, cross-ledger, concurrent, crash/replay, proposal-substitution and result-substitution attacks fail closed;
- the Reconstructor corrected request uses meaningful non-empty regressions, and generic zero-test discovery is fail closed;
- both target PRs remain OPEN + DRAFT + UNMERGED with unchanged reviewed heads and green target CI;
- value, latency, cost-boundary, retry/failure taxonomy, operator/model/version policy and documented limits satisfy G-15 without an unsupported general ROI claim;
- repository closure and Saddle state satisfy G-16;
- no committed document presents historical evidence as current exact-candidate PASS.

The immutable run/artifact/receipt locators for the current exact SHA are written to PR #61 body after the workflows complete. The verifier must resolve them from GitHub rather than trust the body text.

## Completion boundary

Until independent Phase C verifies the exact candidate:

```text
P4: NOT CLAIMED
EXECUTOR 1.0: NOT HUMAN-ACCEPTED
MERGE / RELEASE / DEPLOY / TAG: NOT AUTHORIZED
```

If G-01 through G-16 pass and no false-success path remains, the next gate is the explicit final human `EXECUTOR 1.0: ACCEPT` decision. That decision is not implied by CI, this file, PR metadata or any AI statement.
