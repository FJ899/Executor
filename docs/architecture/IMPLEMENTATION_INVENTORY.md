---
document: "Executor Implementation Inventory"
version: "0.4"
status: "PHASE C FALSE-COMPLETION / CORRECTIVE PHASE B ACTIVE"
date: "2026-08-16"
scope: "current PR #61 implementation state; no P4 completion claim"
repository: "JTJ07/Executor"
baseline: "Phase B work branch from main@5e254811; current head must be resolved from PR #61"
---

# Executor Implementation Inventory v0.4

## 1. Reading rule

This inventory describes the open PR #61 candidate branch. It is not canonical `main`, not a maturity claim and not product acceptance. Exact implementation identity is always the live PR #61 head/tree; immutable runs/artifacts/provider receipts are exact-head evidence only.

Historical rejected exact candidates must never satisfy a later gate:

- `24107bc8a8186ed1928e098118982efb9d62ffaa` — `FALSE-COMPLETION`, replay/global-uniqueness failure;
- `7f662cd487c14d62a4838be8c43cef1358869d50` — `BLOCKED`, G-02/G-14;
- `fdf876e0e2af6d9e4ecea2301ecb686a471037bd` — `FALSE-COMPLETION`, app-mediated GitHub events could be accepted as human;
- `d11f3dd9d6c484a9c554cd562db46c30e0a333fe` — `FALSE-COMPLETION`, decision-freshness TOCTOU between precondition start and later effect authorization.

All ACCEPT comments consumed by those exact candidates are historical provenance only.

## 2. Current implementation boundaries

| Boundary | Current implementation rule | Remaining exact-candidate proof |
|---|---|---|
| GitHub request origin | request actor must match allowed login/id/type/association and `performed_via_github_app` must be present and `null` | verify live request provider records on the final exact head |
| GitHub decision/freeze | ACCEPT/MODIFY/REJECT exact binding plus the same direct-human provider requirement | six new fresh human ACCEPT events are required for the final six-execution series |
| Decision freshness | runtime re-samples real UTC after preconditions at effect authorization; caller/precondition-start clock is not an authority input | adversarial exact-head regression must prove expiry during precondition blocks before AAP/effect reservation and mutation |
| Atomic authority | provider-backed GitHub refs are global one-shot uniqueness; SQLite is crash-safe local evidence/result binding | verify new final-series RESERVED→FINAL chains live and against artifacts |
| Solution proposal | External Intelligence provenance is exact-bound, post-request, zero-human-edit and effect-capability `NONE` | verify in final exact artifacts |
| Input/environment identity | exact source commit/tree, workflow SHA and resolved Docker image are integrity-bound | verify exact final workflow/image/source evidence |
| Runtime | precondition, postcondition, regressions, scope, budgets, link safety, isolation and zero-test fail-closed exist | full exact-head foundation + Docker CI and real-series evidence |
| Result | only review-required/blocked/failed are legal; merge remains false | prove no active false-success path and exact provider/local result binding |
| Real pilots | ScriptOps #8 and Reconstructor #4 remain the bounded reviewed draft outputs | final exact candidate requires a new six-execution authority/evidence series; target heads may remain unchanged if independently verified |
| Value evidence | bounded human review observations exist for the two reviewed patches | exact-head series metrics/failure taxonomy/latency/cost disclosure must satisfy G-15 |
| Repository closure | PR #61 is the implementation path; authority refs are durable receipts | re-check live closure and Saddle at final Phase C |

## 3. Mandatory falsification regressions

### FC-01 — run-id replay

One human decision + one frozen contract produces one stable effect authority key. Changing `run_id` must not create a new effect namespace.

### FC-02 — cross-ledger / cross-runner replay

Provider-backed GitHub authority is the global uniqueness root. A fresh SQLite file, runner, restart or concurrent consumer must not create another legal effect.

### FC-03 — solution provenance

The proposal must bind producer role, provider/model, exact request/source, prompt SHA-256, post-request generation time, `human_solution_edits=0` and `effect_capability=NONE`.

### FC-04 — exact environment identity

Executor SHA, workflow path/SHA, GitHub run/attempt/job and resolved Docker image must be integrity-bound into action/result evidence.

### FC-05 — zero-test regression

A declared unittest-discovery regression is PASS only when output proves at least one test ran. `Ran 0 tests` is BLOCKED.

### FC-06 — direct-human provider provenance

For both request and decision, non-null or missing `performed_via_github_app` must block before verified request/decision, freeze or effect authority.

### FC-07 — expiry crossing during precondition

A decision may be fresh when live-verified and then expire while a legal precondition runs. The runtime must evaluate freshness after preconditions at effect authorization. If expiry has passed, it must stop before AAP/effect authority, mutation and `ACTION_COMPLETED_REVIEW_REQUIRED`.

The public runtime/effect-authorization interface must not expose a caller-controlled clock that can recreate the stale-time path.

## 4. Supported product scope

The human-selected endpoint remains:

- `P4 — REPEATABLE EXECUTOR 1.0`;
- trusted intake: GitHub;
- solution owner: External Intelligence without effect authority;
- authorized pilot repositories: `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`;
- external result endpoint: branch/commit/draft PR only;
- merge/deploy/release/tag/new secrets/new credentials/new paid services: forbidden unless separately authorized.

## 5. Current critical path

```text
D11 FALSE-COMPLETION: EXPIRY TOCTOU
  -> RE-SAMPLE FRESHNESS AT EFFECT AUTHORIZATION
  -> ADVERSARIAL EXPIRY-CROSSING REGRESSION
  -> CANONICAL STATE RECONCILIATION
  -> FULL FOUNDATION / DOCKER / GP001 PROOF
  -> SIX NEW DIRECT-HUMAN ACCEPT EVENTS
  -> ENABLE FINAL EXACT-HEAD P4 SERIES
  -> VERIFY NEW ARTIFACTS + PROVIDER RECEIPTS + TARGET REVIEWS
  -> FRESH INDEPENDENT PHASE C
  -> FINAL HUMAN ACCEPTANCE ONLY IF TECHNICAL PASS
```

The consequential P4 workflow remains disabled while corrective commits and fresh-authority preparation are in progress.

## 6. Stop rule

Do not claim P4, merge PR #61, merge pilot PRs, release, deploy or tag while any selected G-01–G-18 gate remains unproven. Do not weaken the approved DONE definition to make a rejected candidate pass.
