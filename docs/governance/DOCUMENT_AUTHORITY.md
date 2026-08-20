---
document: "Executor Document Authority"
version: "1.3-candidate"
status: "CURRENT-STATE PRECEDENCE RECONCILIATION CANDIDATE"
date: "2026-08-20"
scope: "source-of-truth ownership, precedence and status semantics"
repository: "JTJ07/Executor"
merge_authority: "NONE"
---

# Executor Document Authority v1.3 — candidate

## 1. Purpose

This document answers one question:

> When two Executor records appear to disagree, which source owns which claim?

No single document owns every dimension of Executor. Authority remains subject-specific. This candidate does not change the P4 gate contract or semantic ownership; it only reconciles current-state precedence after the 2026-08-19 finish-line recheck and the fresh run94 reproof.

This file is non-canonical until separately authorized and merged.

## 2. Current technical reproof and historical Human acceptance are different facts

The latest reviewable current-state reconciliation candidate is:

- `evidence/phase-c/P4_RUN94_FINAL_CLAIM_RECONCILIATION_2026-08-20.md`.

It owns the current **technical reproof status** for exact candidate:

```text
HEAD: 3cd0c8d747fef06f82c01cdab8449c7c8a100038
TREE: c739aaa989a15eaed65996d7a0b5242a0ec26d7e
RUN94: 32404181188
TRUSTED READ-ONLY VERIFIER RUN: 32407901358
G-13: PASS
G-15: PASS
G-17: PASS
G-18 FOR 3cd0c8d...: NOT SUPPLIED
```

The following remain authoritative **historical exact-identity facts**:

- `docs/governance/EXECUTOR_1_0_FINAL_COMPLETION_RECORD_2026-08-18.md` — final Human acceptance and integration lineage for the earlier exact candidate `f60829f90ea2f69dc501582daf109b59676be07e`;
- `evidence/phase-c/EXECUTOR_1_0_POST_INTEGRATION_CLOSURE_2026-08-18.md` — post-integration facts for that historical accepted chain;
- `evidence/phase-c/P4_FINISH_LINE_GATE_RECHECK_2026-08-19.md` — dated snapshot that later identified missing finish-line proof and intentionally deferred claim reconciliation.

The 2026-08-18 G-18 decision is preserved; it is not revoked. It is also not inherited by a later exact candidate without a new explicit final Human decision.

```text
HISTORICAL G-18 FACT PRESERVED
!=
G-18 FOR 3cd0c8d... ESTABLISHED
```

## 3. Authority by subject

### Product purpose and ecosystem responsibility

Authoritative source:

- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`.

Owns why Executor exists and its ecosystem responsibility. Executor does not own user goals or strategic direction.

### Human Phase-B authority semantics

Authoritative historical semantic source:

- `PHASE_B_AUTHORIZATION.md`.

Owns the Human-selected DONE/trust/solution/effect boundaries used by the bounded P4 path. Historical authority is not perpetual authority for new effects.

### Completion gates / DONE contract

Authoritative contract:

- `PROJECT_COMPLETION_MAP.md`.

It owns the definitions and ordering of G-01–G-18 and the Human-owned DONE semantics.

Its older terminal-result/status statements record the earlier accepted exact candidate and are historical outcome text after the 2026-08-19 recheck. For current reproof status, the later dated reconciliation record has precedence. The gate definitions themselves are not changed by this candidate.

Required ordering remains:

```text
G-01–G-16
  -> fresh independent G-17
  -> exclusive final Human G-18
  -> project completion
```

### P4 maturity and endpoint evidence semantics

Authoritative source:

- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`.

Owns P-level definitions and required P4 evidence. `ACHIEVED` requires the exact evidence and Human decision required by the ladder; technical CI never self-creates maturity acceptance.

### P4 execution / repeatability policy

Authoritative operational source:

- `docs/product/P4_REPEATABILITY_POLICY.md`.

Owns bounded retry, change-regression, execution-identity binding and CONTRACT_ACCEPT/EFFECT separation. It does not create Human acceptance.

### Request/effect authorization semantics

Authoritative sources:

- `ACTION_AUTHORIZATION_PACKET_v1.0.md`;
- `EXECUTOR_POLICY.yaml`;
- the accepted GitHub trust profile and runtime implementation at the exact implementation SHA being evaluated.

A valid authorization packet is readiness for atomic consumption, not proof of effect, merge authority or product acceptance.

### Architecture

Authoritative source:

- `docs/architecture/EXECUTOR_BUILD_MAP.md`.

Architecture does not prove current maturity.

### Implementation reality

Primary sources:

- exact code/tests/workflows at the evaluated SHA;
- exact GitHub commit/run/artifact/provider evidence;
- `docs/architecture/IMPLEMENTATION_INVENTORY.md` as a dated supporting snapshot.

Repository location does not by itself create semantic ownership.

### Current repository closure

Current reviewable closure record:

- `evidence/phase-c/REPOSITORY_CLOSURE.md`.

For the run94 reconciliation, G-16 cannot become canonical merely because a branch says `PASS`; it requires exact candidate integration plus a fresh read-only live-repository recheck.

### Human-AI deliberation

Authoritative pattern:

- `docs/philosophy/HUMAN_AI_DELIBERATION_MODEL.md`.

It is a working model, not a proof or maturity source.

## 4. Technical PASS versus Human acceptance

These states never collapse:

```text
TECHNICAL PASS
INDEPENDENT VERIFIER PASS
HUMAN TRUST-ROOT ACCEPTANCE
FINAL HUMAN PRODUCT ACCEPTANCE
MERGE AUTHORITY
RELEASE / DEPLOY / TAG AUTHORITY
```

The accepted run94 verifier result can support G-13/G-15/G-17 only because its exact verifier extension and manifest were separately accepted as a trust root. It still cannot create G-18.

## 5. Historical evidence versus current evidence

Exact-SHA evidence remains valid for the identity that produced it even when a later finding supersedes a verdict.

```text
VERDICT SUPERSEDED != EVIDENCE ERASED
```

Consumed authority and historical Human decisions cannot silently become fresh authority for a later exact candidate.

## 6. Repository-state rule

Canonical repository state comes from merged `main`. Open or branch-only reconciliation content is non-canonical unless being reviewed as an exact candidate.

Therefore, while this v1.3 file remains only on a reconciliation branch:

```text
G-02 CANONICAL TRUTH: NOT YET PROMOTED
G-16 REPOSITORY CLOSURE: NOT YET PROMOTED
```

After an exact reconciliation candidate is separately Human-authorized and merged, a fresh read-only exact-main audit must confirm G-02/G-16 before those gates are called `PASS`.

## 7. README rule

`README.md` is navigation and status summary. It does not override dedicated authority sources. It must follow the current precedence above and must not present the historical `f60829f...` G-18 as final acceptance for `3cd0c8d...`.

## 8. Current candidate boundary

```text
SELECTED ENDPOINT: P4 REPEATABLE EXECUTOR 1.0
CURRENT REPROOF TARGET: 3cd0c8d747fef06f82c01cdab8449c7c8a100038
FRESH CONSEQUENTIAL SERIES: PASS / 6 EXECUTIONS
G-13: PASS
G-15: PASS
G-17: PASS
G-02: CANDIDATE / AWAITS CANONICAL INTEGRATION
G-16: CANDIDATE / AWAITS CANONICAL INTEGRATION
G-18 FOR CURRENT REPROOF TARGET: NOT SUPPLIED
PROJECT COMPLETION FOR CURRENT REPROOF TARGET: NOT YET CLAIMED
MERGE: NOT AUTHORIZED
RELEASE: NOT AUTHORIZED
DEPLOYMENT: NOT AUTHORIZED
TAG: NOT AUTHORIZED
NEW CAPABILITY: NOT AUTHORIZED
```

The historical Human-accepted `f60829f...` chain remains historical provenance. This candidate neither deletes it nor uses it to bypass the current exact-candidate gates.
