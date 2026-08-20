---
document: "Executor Document Authority"
version: "1.3"
status: "ACTIVE / RUN94 FINAL HUMAN ACCEPTANCE RECONCILED"
date: "2026-08-20"
scope: "source-of-truth ownership, precedence and status semantics"
repository: "JTJ07/Executor"
---

# Executor Document Authority v1.3

## 1. Purpose

This document answers one question:

> When two repository documents appear to disagree, which document is authoritative for which kind of claim?

No single document owns every dimension of Executor. Authority is assigned by subject so architecture, implementation status, Human authorization semantics and maturity do not silently overwrite one another.

The repository has reached a later state than the Phase-B snapshot and the earlier 2026-08-18 acceptance/integration chain preserved in historical records. Current completion facts must therefore be read from the current Run94 final Human-acceptance record before interpreting older status text.

## 2. Authority by subject

### Current product completion and Human acceptance

Authoritative current record:

- `docs/governance/EXECUTOR_1_0_FINAL_HUMAN_ACCEPTANCE_RECORD_2026-08-20.md`.

Supporting current Run94 closure record:

- `evidence/phase-c/P4_RUN94_FINAL_CLOSURE_RECONCILIATION_2026-08-20.md`.

Historical 2026-08-18 acceptance/integration records retained for provenance:

- `docs/governance/EXECUTOR_1_0_FINAL_COMPLETION_RECORD_2026-08-18.md`;
- `evidence/phase-c/EXECUTOR_1_0_POST_INTEGRATION_CLOSURE_2026-08-18.md`.

The current record owns the latest exact Human-accepted implementation, G-18 result and current completion pointer. The Run94 closure record owns the canonical pre-G-18 G-01–G-17/G-02/G-16 state. The 2026-08-18 records remain authoritative historical facts for their own exact identities and are not rewritten.

Current terminal facts:

```text
SELECTED ENDPOINT: P4 REPEATABLE EXECUTOR 1.0
PRODUCT / COMPLETION: HUMAN ACCEPTED
PROJECT COMPLETION: PASS
G-01–G-18: PASS
IMPLEMENTATION INTEGRATION: COMPLETE
EXACT HUMAN-ACCEPTED CANDIDATE: 3cd0c8d747fef06f82c01cdab8449c7c8a100038
EXACT HUMAN-ACCEPTED TREE: c739aaa989a15eaed65996d7a0b5242a0ec26d7e
FRESH CONSEQUENTIAL RUN: 32404181188
TRUSTED INDEPENDENT VERIFIER RUN: 32407901358
CANONICAL MAIN AT FINAL ACCEPTANCE: a7fc272e09a2ffb5c06a98e26ed6ef9667cd4f89
ACTIVE COMPLETION GATE: NONE
```

The accepted implementation identity and canonical-main identity are intentionally different facts. The canonical `main` state contains the accepted implementation plus later governance/evidence reconciliation; it does not rewrite which exact implementation the Human accepted.

### Product purpose and ecosystem responsibility

Authoritative source:

- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`.

Owns why Executor exists, its ecosystem responsibility and the boundary that Executor does not own user goals or strategic decisions. It does not override later current completion facts.

### Human Phase-B authority semantics

Authoritative historical semantic source:

- `PHASE_B_AUTHORIZATION.md`.

Owns the Human-selected DONE/trust/solution/effect boundaries and the revocation-cutoff semantics used to construct and verify the accepted product path. Phase B is no longer current execution state; these decisions remain provenance and semantic constraints for the accepted evidence chains.

### Completion gates / DONE contract

Authoritative contract:

- `PROJECT_COMPLETION_MAP.md`.

Owns the selected DONE gates G-01–G-18, adaptive completion-control decision and distinction between implementation evidence, independent verification and final Human acceptance. Its Phase-A/Phase-B work maps and gap inventories are historical provenance after final completion. Current gate outcome is supplied by the 2026-08-20 final Human-acceptance record:

```text
G-01–G-18: PASS
PROJECT COMPLETION: PASS
```

Where older text says Phase B active, P4 not claimed, G-18 open or final acceptance unavailable, that text is a historical checkpoint and must not be interpreted as current state unless it is explicitly describing the pre-G-18 Run94 reconciliation point.

### P4 operational semantics

Authoritative operational policy:

- `docs/product/P4_REPEATABILITY_POLICY.md`.

Owns bounded P4 retry, repeatability, `CONTRACT_ACCEPT`/EFFECT separation, revocation-cutoff execution semantics, failure classification and series requirements. It does not itself create Human acceptance or new consequential authority.

### Architecture / Build Map

Authoritative source:

- `docs/architecture/EXECUTOR_BUILD_MAP.md`.

Owns architectural classification of Executor components and the distinction between architecture and maturity. It does not prove implementation or current completion status.

### Build-order history

Source:

- `docs/EXECUTOR_BUILD_ORDER.md`.

It owns historical implementation sequencing only where consistent with later Human authorization and exact accepted evidence. It is not a current task queue after Executor 1.0 completion.

### Implementation reality

Primary dated snapshot:

- `docs/architecture/IMPLEMENTATION_INVENTORY.md`.

Supporting truth:

- exact code/tests at the relevant SHA;
- exact GitHub PR/commit/workflow evidence.

The inventory is a dated snapshot. Historical/open candidates do not override current `main` or the current accepted evidence chain.

### Product maturity and proof terminology

Authoritative source:

- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`.

Owns P-level definitions/evidence terminology. The selected P4 claim is current only because its required evidence and final Human acceptance were established independently; the ladder itself cannot turn CI success into acceptance.

### Human-AI deliberation

Authoritative pattern:

- `docs/philosophy/HUMAN_AI_DELIBERATION_MODEL.md`.

It is a cross-cutting working model, not a maturity axis or proof source.

### Action Authorization Packet

Authoritative semantic contract:

- `ACTION_AUTHORIZATION_PACKET_v1.0.md`.

A valid AAP means only that an exact action packet is ready for governed atomic consumption. It is not proof that the action happened, product acceptance or permission to merge/deploy/release.

## 3. Technical PASS versus product acceptance

`PASS` may be a test result or specifically defined internal technical state. It never means by itself:

```text
HUMAN ACCEPTED
PRODUCT ACCEPTED
MERGED
MATURITY LEVEL ACHIEVED
```

Executor 1.0 is currently Human-accepted because the fresh Run94 consequential evidence chain, the separately accepted read-only trusted-verifier chain, the canonical closure state, and the direct Human G-18 decision all exist. No single technical PASS self-certifies the product claim.

## 4. Historical evidence versus current evidence

Exact-SHA evidence remains valid historical evidence for the SHA that produced it even when a later finding or later acceptance chain advances the current pointer.

```text
VERDICT SUPERSEDED != EVIDENCE ERASED
HISTORICAL ACCEPTANCE PRESERVED != CURRENT ACCEPTANCE POINTER UNCHANGED
```

Historical runs, artifacts, provider receipts and consumed Human decisions cannot silently become fresh authority. The earlier P4 series at `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` remains historical-only. The separately Human-accepted 2026-08-18 candidate `f60829f90ea2f69dc501582daf109b59676be07e` remains historical provenance for that exact chain. The current Run94 Human-accepted identity is `3cd0c8d747fef06f82c01cdab8449c7c8a100038`.

## 5. Repository-state rule

Canonical repository state comes from merged `main`. Open/draft branch content is non-canonical unless an exact candidate is explicitly being reviewed. Current product completion is a Human acceptance fact bound to the exact accepted implementation and evidence chain; governance-only persistence or later `main` movement may record and preserve that fact but may not silently retarget the accepted implementation identity.

## 6. README rule

`README.md` is navigation and current-status summary. It points to authoritative sources but does not override them. If README conflicts with a dedicated authority source, the dedicated source wins and README must be corrected.

## 7. Naming rule: v1 versus maturity P-levels

`v1` in a filename identifies a document/product-slice version. It does not by itself mean `Executor 1.0`, P4 or production readiness. The current P4/Executor 1.0 claim is valid only through the accepted evidence/verification/Human-decision chain.

## 8. Current terminal boundary

```text
CURRENT HUMAN-ACCEPTED TARGET: P4 REPEATABLE EXECUTOR 1.0
CURRENT HUMAN-ACCEPTED IMPLEMENTATION: 3cd0c8d747fef06f82c01cdab8449c7c8a100038
PRODUCT ACCEPTANCE: COMPLETE
PROJECT COMPLETION: PASS
G-01–G-18: PASS
IMPLEMENTATION INTEGRATION: COMPLETE
CANONICAL MAIN AT FINAL ACCEPTANCE: a7fc272e09a2ffb5c06a98e26ed6ef9667cd4f89
ACTIVE COMPLETION GATE: NONE
ACTIVE PHASE-B IMPLEMENTATION PATH: NONE
FURTHER MERGE: NOT AUTHORIZED
RELEASE: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
TAG: NOT AUTHORIZED
TARGET PILOT PR MERGES: NOT AUTHORIZED
NEW SECRETS / CREDENTIALS / PAID SERVICES: NOT AUTHORIZED
BROADER EXTERNAL EFFECTS: NOT AUTHORIZED
```

Future merge, release, deployment, tag, pilot merge or new product-development work is a new phase requiring separate authority; silence or prior P4 acceptance is not authority for those effects.
