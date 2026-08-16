---
document: "Executor Implementation Inventory"
version: "0.3"
status: "PHASE C REJECTED / CORRECTIVE PHASE B ACTIVE"
date: "2026-08-16"
scope: "current PR #61 implementation state; no P4 completion claim"
repository: "JTJ07/Executor"
baseline: "Phase B work branch from main@5e254811; current head must be resolved from PR #61"
---

# Executor Implementation Inventory v0.3

## 1. Reading rule

This inventory is a current implementation snapshot for the open Phase-B candidate. It is not canonical `main`, not a maturity claim, and not product acceptance.

Independent Phase C rejected historical candidate `24107bc8a8186ed1928e098118982efb9d62ffaa` as `FALSE-COMPLETION`. All successful runs and artifacts tied to that SHA are historical rejected-candidate evidence only.

## 2. Current state

| Boundary | Current PR #61 state | Remaining proof |
|---|---|---|
| GitHub request origin | direct-human issues #62/#63 were observed and exact actor/body/source binding was independently verified | corrected final series needs fresh direct-human request/decision events where required |
| GitHub decision/freeze | ACCEPT/MODIFY/REJECT verification exists; old local-only one-shot design was rejected | corrective branch now requires provider-backed global GitHub consumption; adversarial proof still required |
| Atomic authority | SQLite WAL/`BEGIN IMMEDIATE` still provides local crash-safe binding | local DB is no longer allowed to be the sole uniqueness boundary; cross-runner/cross-ledger replay must be proven impossible |
| Solution proposal | bounded authority-free proposal interface exists | post-request External Intelligence provenance, model and prompt hash are now required and must be proven on final pilots |
| Execution environment | Docker isolation, no network/secrets and cleanup exist | exact workflow SHA and resolved Docker image ID are now explicit effect evidence and must be verified on the final candidate |
| Runtime | exact source, precondition, postcondition, regressions, scope and patch-budget enforcement exist | zero-test unittest discovery now fails closed; corrected Reconstructor request/evidence is still required |
| Result | only review-required/blocked/failed are legal; merge remains false | global authority receipt and complete exact-environment binding must appear in final durable artifacts |
| Real pilots | ScriptOps PR #8 and Reconstructor PR #4 exist, remain draft/unmerged, and were human-approved | both belong to a rejected Executor candidate; they do not prove corrected P4 completion |
| Value evidence | two human reviews and bounded human-time comparison are recorded | P4 requires a larger real-task series, repeatability/failure taxonomy, model/dependency policy and bounded cost/latency disclosure |
| Repository closure | obsolete Executor PRs were closed; issue #35 closed; PR #61 is the active completion path | provider authority refs are durable evidence refs, not unfinished implementation branches, and must not be deleted as cleanup |

## 3. Phase-C falsification that constrains the current implementation

### FC-01 — same-ledger replay by changing `run_id`

Rejected behavior: effect `packet_id` depended on caller-controlled `run_id`, so another run ID created a new legal AAP key.

Current corrective invariant:

```text
ONE HUMAN DECISION EVIDENCE REF + ONE FROZEN CONTRACT
  -> ONE STABLE EFFECT AUTHORITY KEY
```

`run_id` may identify an execution attempt; it may not create new effect authority.

### FC-02 — cross-ledger replay

Rejected behavior: an arbitrary fresh SQLite file created an empty authority namespace.

Current corrective invariant:

```text
GITHUB PROVIDER AUTHORITY RECEIPT = GLOBAL ONE-SHOT NAMESPACE
LOCAL SQLITE = LOCAL CRASH-SAFE MIRROR / RESULT EVIDENCE
```

A different runner or local ledger path must observe the same consumed global authority.

### FC-03 — missing solution provenance

Rejected behavior: full replacement candidates existed without durable proof that External Intelligence produced/re-derived them after the human request.

Current corrective invariant:

- producer role = `EXTERNAL_INTELLIGENCE`;
- provider/model recorded;
- exact request + target source bound;
- prompt SHA-256 recorded;
- generation time later than the human request;
- `human_solution_edits = 0`;
- proposer effect capability = `NONE`.

### FC-04 — environment identity only in logs

Rejected behavior: workflow/image identity could be reconstructed from hosted-runner logs but was absent from action/result integrity.

Current corrective invariant:

- exact Executor commit;
- exact workflow path and workflow file SHA-256;
- exact GitHub run/attempt/job;
- exact resolved Docker `sha256:` image ID;
- environment digest bound into the action authorization payload and full identity copied into terminal evidence.

### FC-05 — silent zero-test regression

Rejected behavior: `unittest discover` returned exit 0 while running zero tests and the aggregate report said regressions PASS.

Current corrective invariant:

> A declared unittest-discovery regression is PASS only if its output proves that at least one test ran.

A zero-test result is `BLOCKED`, never PASS.

## 4. Supported candidate scope

The human-selected product endpoint and semantic constraints remain unchanged:

- endpoint: `P4 — REPEATABLE EXECUTOR 1.0`;
- trusted intake: GitHub;
- solution owner: External Intelligence, without effect authority;
- authorized external repositories: `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`;
- result endpoint: dedicated branch/commit/draft PR only;
- merge/deploy/release/new secrets/new credentials/new paid services: forbidden unless separately authorized.

## 5. What exists on canonical main

Canonical `main` remains the pre-Phase-B baseline. M0/M1/M2 bounded governance, state, policy, Docker isolation, GP001 controlled execution/replay and request-formation foundations remain the accepted baseline. PR #61 is non-canonical candidate work until a later explicit merge decision.

## 6. Current critical path

```text
PHASE C FALSE-COMPLETION
  -> GLOBAL ONE-SHOT AUTHORITY REWORK
  -> PROVENANCE + ENVIRONMENT BINDING
  -> ZERO-TEST FAIL-CLOSED
  -> FOUNDATION / ADVERSARIAL CI
  -> CORRECTED DIRECT-HUMAN PILOT REQUESTS
  -> FRESH ACCEPTS
  -> NEW EXACT-HEAD REAL PILOT SERIES
  -> HUMAN REVIEWS + P4 SERIES METRICS
  -> FRESH INDEPENDENT PHASE C
  -> FINAL HUMAN ACCEPTANCE
```

The pilot execution workflow remains intentionally disabled during corrective commits so historical/expired authority cannot fire.

## 7. Stop rule

Do not claim P4, merge PR #61, merge pilot PRs, release or deploy while any selected G-01–G-18 gate remains unproven.

Do not weaken the approved DONE definition to make the rejected candidate pass.
