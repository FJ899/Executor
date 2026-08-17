---
document: "Executor Document Authority"
version: "1.1"
status: "ACTIVE / HUMAN GOVERNANCE RECONCILED"
date: "2026-08-17"
scope: "source-of-truth ownership, precedence and status semantics"
repository: "JTJ07/Executor"
---

# Executor Document Authority v1.1

## 1. Purpose

This document answers one question:

> When two repository documents appear to disagree, which document is authoritative for which kind of claim?

No single document owns every dimension of Executor. Authority is assigned by subject so architecture, implementation status, human authorization semantics and maturity do not silently overwrite one another.

## 2. Authority by subject

### Product purpose and ecosystem responsibility

Authoritative source:

- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`

Owns why Executor exists, its ecosystem responsibility and the boundary that Executor does not own user goals or strategic decisions. It does not own current implementation inventory, current build sequence, maturity proof or later dedicated authority semantics.

### Human Phase-B authority semantics

Authoritative source:

- `PHASE_B_AUTHORIZATION.md`.

Owns the human-selected DONE/trust/solution/effect boundaries and later explicit human semantic decisions made inside Phase B, including the 2026-08-17 revocation cutoff:

`FINAL LIVE VERIFICATION AS REVOCATION CUTOFF BOUND INTO SUCCESSFUL GLOBAL CONTRACT_ACCEPT CONSUMPTION`.

Operational implementation/policy may realize this meaning but may not weaken or silently reinterpret it.

### Completion gates

Authoritative source:

- `PROJECT_COMPLETION_MAP.md`.

Owns the selected DONE gates G-01–G-18 and the distinction between implementation evidence, independent verification and final human acceptance. Where a later explicit human decision in `PHASE_B_AUTHORIZATION.md` refines a gate's semantics, the completion map must record that refinement and the explicit human decision wins over older ambiguous wording.

### P4 operational semantics

Authoritative operational policy:

- `docs/product/P4_REPEATABILITY_POLICY.md`.

Owns bounded P4 retry, repeatability, `CONTRACT_ACCEPT`/EFFECT separation, revocation-cutoff execution semantics, failure classification and series requirements. It does not itself authorize human decisions or consequential effects.

### Architecture / Build Map

Authoritative source:

- `docs/architecture/EXECUTOR_BUILD_MAP.md`.

Owns architectural classification of Executor components and the distinction between architecture and maturity. It does not prove implementation.

### Current build sequence

Authoritative source:

- `docs/EXECUTOR_BUILD_ORDER.md`.

Owns the current critical implementation path when consistent with later human authorization and the current implementation inventory. A stale historical build-order statement cannot override a later human semantic decision or exact implementation evidence.

### Implementation reality

Primary dated snapshot:

- `docs/architecture/IMPLEMENTATION_INVENTORY.md`.

Supporting truth:

- exact code/tests at the candidate SHA;
- exact GitHub PR/commit/workflow evidence.

The inventory is a dated snapshot. Open branches and PRs remain non-canonical relative to `main`, but they are the authoritative implementation candidate state when an exact open PR head is explicitly under review. A technical claim must still be supported by the exact code/tests/evidence for that SHA.

### Product maturity and proof

Authoritative source:

- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`.

Owns P-level definitions/evidence terminology. The ladder does not select current implementation work and cannot turn CI success into human acceptance.

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

Product/maturity acceptance requires the exact evidence and human decision defined by the governing completion map and maturity contract.

## 4. Historical evidence versus current evidence

Exact-SHA evidence remains valid historical evidence for the SHA that produced it even when a later finding supersedes the verdict.

```text
VERDICT SUPERSEDED != EVIDENCE ERASED
```

Historical runs, artifacts, provider receipts and consumed human decisions cannot silently satisfy a later exact-candidate gate. In particular, the P4 series executed for `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` is historical-only after the later G-04 revocation-cutoff finding.

## 5. Repository-state rule

Canonical repository state comes from merged `main`. The following are non-canonical until merged:

- draft/open PR content;
- branch-only documents;
- mutable PR descriptions/comments;
- generated candidate artifacts.

For an explicitly reviewed candidate such as PR #61, the live exact head/tree defines candidate implementation identity, while immutable exact-head workflows/artifacts/provider receipts establish post-commit facts. Mutable PR prose is locator/status metadata only.

## 6. README rule

`README.md` is navigation and current-status summary. It points to authoritative sources but does not override them. If README conflicts with a dedicated authority source, the dedicated source wins and README must be corrected.

## 7. Naming rule: v1 versus maturity P-levels

`v1` in a filename identifies a document/product-slice version. It does not mean `Executor 1.0`, P4 or production readiness. Maturity is claimed only through the applicable evidence gates and final human acceptance.

## 8. Current candidate boundary

```text
CURRENT HUMAN-SELECTED TARGET: P4 REPEATABLE EXECUTOR 1.0
ACTIVE IMPLEMENTATION PATH: PR #61 / DRAFT / OPEN / UNMERGED
REVOCATION CUTOFF: HUMAN-APPROVED / FINAL LIVE VERIFIED SNAPSHOT + SUCCESSFUL GLOBAL CONTRACT_ACCEPT
OLD eca7eeb P4 SERIES: HISTORICAL EVIDENCE ONLY
NEW CONSEQUENTIAL SERIES: REQUIRES FRESH HUMAN AUTHORITY LATER
P4: NOT CLAIMED
PHASE C: REQUIRED AFTER NEW CONSEQUENTIAL EVIDENCE
FINAL HUMAN ACCEPTANCE: NOT AVAILABLE
```
