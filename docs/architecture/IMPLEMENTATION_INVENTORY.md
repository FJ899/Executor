---
document: "Executor Implementation Inventory"
version: "0.6"
status: "CORRECTIVE PHASE B / REVOCATION CUTOFF IMPLEMENTATION"
date: "2026-08-17"
scope: "current PR #61 implementation state; no P4 completion claim"
repository: "JTJ07/Executor"
baseline: "corrective candidate descends from eca7eebbb4bead819cfd35ecd81b3200cc6e461a"
---

# Executor Implementation Inventory v0.6

## 1. Reading rule

This inventory describes the open PR #61 candidate branch. It is not canonical `main`, not a maturity claim and not product acceptance. Exact implementation identity is always the live PR #61 head/tree. Immutable runs/artifacts/provider receipts are evidence only for the exact SHA that produced them.

Historical or superseded exact candidates do not satisfy a later exact-candidate gate. Their raw evidence is preserved rather than erased.

- `24107bc8a8186ed1928e098118982efb9d62ffaa` — `FALSE-COMPLETION`, replay/global-uniqueness failure;
- `7f662cd487c14d62a4838be8c43cef1358869d50` — `BLOCKED`, G-02/G-14;
- `fdf876e0e2af6d9e4ecea2301ecb686a471037bd` — `FALSE-COMPLETION`, app-mediated GitHub events could be accepted as human;
- `d11f3dd9d6c484a9c554cd562db46c30e0a333fe` — `FALSE-COMPLETION`, effect-freshness TOCTOU;
- `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` — the six-run P4 series DID execute and produced raw exact-SHA evidence, but the later G-04 finding showed that mutable GitHub request/comment currentness did not yet have the now-approved contract-freeze revocation cutoff. The old technical evidence remains historical evidence for `eca7eeb...`; its prior completion verdict is superseded and it cannot satisfy a new candidate.

Every human ACCEPT consumed by those exact candidates, including ACCEPT 001–012, is historical/consumed authority only and must not be reused.

`VERDICT superseded != EVIDENCE erased`.

## 2. Current implementation boundaries

| Boundary | Current implementation rule | Remaining exact-candidate proof |
|---|---|---|
| GitHub request origin | request actor must match allowed login/id/type/association and `performed_via_github_app` must be present and `null` | re-prove through new final-live snapshot tests and later fresh exact-series evidence |
| GitHub decision/freeze | `github-pilot-decide` performs final live request+decision verification immediately before `CONTRACT_ACCEPT`; exact provider evidence is snapshotted and SHA-bound into global consumption; only successful binding creates `AUTHORIZED_AND_FROZEN` | FC-09–FC-17 + exact-head non-consequential CI now; fresh real ACCEPT series later |
| Revocation cutoff | PRE-CUTOFF provider edit/delete/mismatch/expiry blocks. Failed global consumption creates no authority and retry requires new final verification. POST-CUTOFF mutation does not retroactively revoke a successfully frozen contract | verify adversarial matrix and independent replay of snapshot/receipt relationship |
| Stage-B authority source | `run-pilot` validates immutable frozen request/decision snapshot plus successful FINAL `CONTRACT_ACCEPT` local/global receipts; mutable issue/comment currentness is not a post-cutoff revocation source | prove no live trust re-fetch in run-pilot and replay frozen evidence independently |
| EFFECT freshness | runtime re-samples UTC after preconditions; frozen decision expiry is effect receipt `not_after`; provider reservation `committer.date` must be `< not_after` | preserve existing expiry/provider-time regressions and later fresh receipts |
| Atomic authority | provider-backed GitHub refs are global one-shot uniqueness; SQLite is crash-safe local evidence/result binding | preserve concurrent/replay/crash/result-binding tests for both contract and effect authority |
| Solution proposal | External Intelligence provenance is exact-bound, post-request, zero-human-edit and effect-capability `NONE` | preserve exact-head tests and later fresh artifact verification |
| Input/environment identity | exact source commit/tree, workflow SHA and resolved Docker image are integrity-bound | exact-head foundation/GP001 now; later fresh P4 workflow/image/source evidence |
| Runtime | precondition, postcondition, regressions, scope, budgets, link safety, isolation and zero-test fail-closed exist | full foundation + Docker/security CI |
| Result | only review-required/blocked/failed are legal; merge remains false | preserve no-false-success and exact result binding |
| Real pilots | ScriptOps #8 and Reconstructor #4 remain bounded reviewed draft outputs | no new consequential series in this corrective step; target heads remain historical/review evidence until fresh proof |
| Value evidence | bounded human review observations remain historical observations | fresh exact-candidate consequential proof must be generated later before G-15 can pass |
| Repository closure | PR #61 remains the implementation path; authority refs are durable receipts | re-check PR/pilot/Saddle state after exact-head non-consequential CI |

## 3. Mandatory falsification regressions

Existing FC-01–FC-08 remain mandatory:

- FC-01 run-id replay;
- FC-02 cross-ledger/cross-runner replay;
- FC-03 solution provenance;
- FC-04 exact environment identity;
- FC-05 zero-test regression;
- FC-06 direct-human provider provenance;
- FC-07 expiry crossing during precondition;
- FC-08 provider-time expiry.

The accepted revocation cutoff adds:

### FC-09 — PRE-CUTOFF ACCEPT EDIT
Edited exact ACCEPT before final live verification blocks before `CONTRACT_ACCEPT`; no frozen contract.

### FC-10 — PRE-CUTOFF ACCEPT DELETE
Deleted exact ACCEPT before final live verification blocks before `CONTRACT_ACCEPT`; no frozen contract.

### FC-11 — PRE-CUTOFF REQUEST MUTATION
A materially changed request invalidates the old decision/draft binding. The old decision cannot authorize the changed request.

### FC-12 — FINAL VERIFY + FAILED GLOBAL CONSUMPTION
A successful final live verification whose global `CONTRACT_ACCEPT` consumption fails creates no authority. Retry requires fresh provider verification; the failed snapshot is not dormant authority.

### FC-13 — POST-CUTOFF ACCEPT EDIT
After successful `CONTRACT_ACCEPT` freeze, later ACCEPT edit does not retroactively revoke the frozen authority. Normal EFFECT controls still apply.

### FC-14 — POST-CUTOFF ACCEPT DELETE
After successful freeze, later deletion of the original ACCEPT does not retroactively revoke the frozen authority.

### FC-15 — POST-CUTOFF REQUEST EDIT
After successful freeze, later request edit does not change the frozen request snapshot or contract meaning.

### FC-16 — SNAPSHOT SUBSTITUTION
Altered snapshot/hash/provider identity that does not match the consumed `CONTRACT_ACCEPT` receipt blocks.

### FC-17 — CONTRACT_ACCEPT REPLAY
Same consumed `CONTRACT_ACCEPT` cannot produce another freeze via different `run_id`, fresh SQLite or another consumer where provider one-shot state is shared.

## 4. Supported product scope

The human-selected endpoint remains:

- `P4 — REPEATABLE EXECUTOR 1.0`;
- trusted intake: GitHub;
- solution owner: External Intelligence without effect authority;
- authorized pilot repositories: `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`;
- external result endpoint: branch/commit/draft PR only;
- merge/deploy/release/tag/new secrets/new credentials/new paid services: forbidden unless separately authorized.

No scope or ownership expansion is introduced by the revocation-cutoff correction.

## 5. Consequential workflow state

The old six-run series for `eca7eeb...` ran successfully as a workflow and remains immutable historical raw evidence for that exact SHA. It is not current consequential proof after the later G-04 finding.

The P4 real-pilot workflow is now **manual `workflow_dispatch` only** and requires six explicitly supplied fresh ACCEPT comment IDs. A PR-head `synchronize` event must not execute the consequential series and the workflow must not contain the historical ACCEPT 001–012 IDs.

This corrective step stops before fresh human authority. No new six-run series is authorized or run here.

## 6. Current critical path

```text
HUMAN-APPROVED REVOCATION CUTOFF
  -> FINAL-LIVE SNAPSHOT + CONTRACT_ACCEPT BINDING
  -> POST-CUTOFF FROZEN-AUTHORITY EXECUTION SOURCE
  -> FC-09..FC-17
  -> G-02 CURRENT-STATE RECONCILIATION
  -> FULL NON-CONSEQUENTIAL FOUNDATION / DOCKER / GP001 PROOF
  -> STOP BEFORE FRESH HUMAN AUTHORITY
  -> SIX NEW DIRECT-HUMAN ACCEPT EVENTS (LATER, HUMAN)
  -> MANUAL NEW EXACT-HEAD P4 SERIES (LATER)
  -> FRESH INDEPENDENT PHASE C (LATER)
  -> FINAL HUMAN ACCEPTANCE ONLY IF ALL GATES PASS
```

## 7. Stop rule

Do not claim P4, merge PR #61, merge pilot PRs, release, deploy or tag while any selected G-01–G-18 gate remains unproven. Do not weaken the approved DONE definition to make a rejected/superseded candidate pass.
