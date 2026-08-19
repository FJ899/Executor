---
document: "Executor Document Authority"
version: "1.2"
status: "ACTIVE / FINAL COMPLETION RECONCILED"
date: "2026-08-19"
scope: "source-of-truth ownership, precedence and status semantics"
repository: "JTJ07/Executor"
---

# Executor Document Authority v1.2

## 1. Purpose

This document answers one question:

> When two repository documents appear to disagree, which document is authoritative for which kind of claim?

No single document owns every dimension of Executor. Authority is assigned by subject so architecture, implementation status, Human authorization semantics and maturity do not silently overwrite one another.

The repository has reached a later state than the Phase-B snapshot preserved in several historical planning documents. Current completion facts must therefore be read from the final completion/integration records before interpreting older Phase-B status text.

## 2. Authority by subject

### Current product completion and Human acceptance

Authoritative current records:

- `docs/governance/EXECUTOR_1_0_FINAL_COMPLETION_RECORD_2026-08-18.md`;
- `evidence/phase-c/EXECUTOR_1_0_POST_INTEGRATION_CLOSURE_2026-08-18.md`.

They own the final exact accepted candidate, G-01–G-18 result, Human G-18 acceptance, verified integration lineage and current closure meaning.

Current terminal facts:

```text
SELECTED ENDPOINT: P4 REPEATABLE EXECUTOR 1.0
PRODUCT / COMPLETION: HUMAN ACCEPTED
PROJECT COMPLETION: PASS
G-01–G-18: PASS
IMPLEMENTATION INTEGRATION: COMPLETE
EXACT HUMAN-ACCEPTED CANDIDATE: f60829f90ea2f69dc501582daf109b59676be07e
CURRENT MAIN AFTER POST-INTEGRATION CLOSURE: d115578cf05ed7edf55c50a2b5d29af16d13fb4d
```

The accepted candidate identity and later current-main identity are intentionally different facts. The later integration/closure SHA does not rewrite which exact candidate the Human accepted.

### Product purpose and ecosystem responsibility

Authoritative source:

- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`.

Owns why Executor exists, its ecosystem responsibility and the boundary that Executor does not own user goals or strategic decisions. It does not override later current completion facts.

### Human Phase-B authority semantics

Authoritative historical semantic source:

- `PHASE_B_AUTHORIZATION.md`.

Owns the Human-selected DONE/trust/solution/effect boundaries and the revocation-cutoff semantics used to construct and verify the accepted candidate. Phase B is no longer current execution state; these decisions remain provenance and semantic constraints for the accepted evidence chain.

### Completion gates / DONE contract

Authoritative contract:

- `PROJECT_COMPLETION_MAP.md`.

Owns the selected DONE gates G-01–G-18, adaptive completion-control decision and distinction between implementation evidence, independent verification and final Human acceptance. Its Phase-A/Phase-B work maps and gap inventories are historical provenance after final completion. Current gate outcome is supplied by the final completion record:

```text
G-01–G-18: PASS
PROJECT COMPLETION: PASS
```

Where older text says Phase B active, P4 not claimed or final acceptance unavailable, that text is a historical checkpoint and must not be interpreted as current state.

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

The inventory is a dated snapshot. Historical/open candidates do not override current `main` or the final accepted/integration evidence chain.

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

Executor 1.0 is Human-accepted because the independent Phase-C chain plus the direct Human G-18 provider fact exists, not because any single technical PASS self-certified it.

## 4. Historical evidence versus current evidence

Exact-SHA evidence remains valid historical evidence for the SHA that produced it even when a later finding supersedes the verdict.

```text
VERDICT SUPERSEDED != EVIDENCE ERASED
```

Historical runs, artifacts, provider receipts and consumed Human decisions cannot silently become fresh authority. The earlier P4 series at `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` remains historical-only. The accepted product identity is the later exact candidate `f60829f...`.

## 5. Repository-state rule

Canonical repository state comes from merged `main`. Open/draft branch content is non-canonical unless an exact candidate is explicitly being reviewed. Current product completion, however, is a historical acceptance fact bound to the accepted exact candidate and preserved through verified integration; it is not re-decided merely because `main` later advances with governance-only closure records.

## 6. README rule

`README.md` is navigation and current-status summary. It points to authoritative sources but does not override them. If README conflicts with a dedicated authority source, the dedicated source wins and README must be corrected.

## 7. Naming rule: v1 versus maturity P-levels

`v1` in a filename identifies a document/product-slice version. It does not by itself mean `Executor 1.0`, P4 or production readiness. The current P4/Executor 1.0 claim is valid only through the final evidence/acceptance chain.

## 8. Current terminal boundary

```text
CURRENT HUMAN-ACCEPTED TARGET: P4 REPEATABLE EXECUTOR 1.0
PRODUCT ACCEPTANCE: COMPLETE
PROJECT COMPLETION: PASS
IMPLEMENTATION INTEGRATION: COMPLETE
ACTIVE COMPLETION GATE: NONE
ACTIVE PHASE-B IMPLEMENTATION PATH: NONE
RELEASE: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
TAG: NOT AUTHORIZED
TARGET PILOT PR MERGES: NOT AUTHORIZED
NEW SECRETS / CREDENTIALS / PAID SERVICES: NOT AUTHORIZED
BROADER EXTERNAL EFFECTS: NOT AUTHORIZED
```

Future release, deployment, tag, pilot merge or new product-development work is a new phase requiring separate authority; silence or prior P4 acceptance is not authority for those effects.
