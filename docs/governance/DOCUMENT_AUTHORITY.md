---
document: "Executor Document Authority"
version: "1.0"
status: "PROPOSED AUTHORITY RECONCILIATION / PENDING HUMAN REVIEW"
date: "2026-08-09"
scope: "source-of-truth ownership, precedence and status semantics"
repository: "litrgratis-pixel/Executor"
---

# Executor Document Authority v1

## 1. Purpose

This document answers one question:

> When two repository documents appear to disagree, which document is authoritative for which kind of claim?

No single document owns every dimension of Executor. Authority is assigned by subject so that architecture, implementation status and maturity do not silently overwrite one another.

## 2. Authority by subject

### Product purpose and ecosystem responsibility

Authoritative source:

- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`

Owns:

- why Executor exists;
- relationship to Human, Ginseng, Creative OS / canon and deliberation;
- the boundary that Executor does not own user goals or strategic decisions.

Does not own:

- current implementation inventory;
- current build sequence after the accepted Build Order baseline;
- maturity proof status;
- detailed semantics of a component that received a later dedicated frozen contract.

### Architecture / Build Map

Authoritative source:

- `docs/architecture/EXECUTOR_BUILD_MAP.md`

Owns:

- architectural classification of Executor components;
- Foundation, Core Structure, Execution Infrastructure, Capability Modules, UX and Extensions;
- the distinction between architecture and maturity.

Does not prove that any component is implemented.

### Current build sequence

Authoritative source:

- `docs/EXECUTOR_BUILD_ORDER.md`

Owns:

- the current critical implementation path;
- GP001-first sequencing;
- which work is deferred from the critical path.

If an older document describes a different historical implementation order, `EXECUTOR_BUILD_ORDER.md` wins for current work order.

### Implementation reality

Primary snapshot:

- `docs/architecture/IMPLEMENTATION_INVENTORY.md`

Supporting truth:

- merged code and tests on `main`;
- exact merged PR / commit evidence.

Inventory is a dated snapshot, not permanent authority. A claim that something is implemented must be supported by merged repository state. Open branches and draft PRs do not change `main` implementation status.

### Product maturity and proof

Authoritative source:

- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`

Owns:

- definitions of P0, P1, P2, P3 and later maturity levels;
- evidence required to claim those levels;
- maturity/proof terminology.

The ladder does **not** select the current implementation task. Build order and maturity are separate concerns.

Current critical path may therefore work on GP001 while no new maturity level is being claimed.

### Human-AI deliberation

Authoritative pattern:

- `docs/philosophy/HUMAN_AI_DELIBERATION_MODEL.md`

Owns:

- recommendation / critique / synthesis role boundaries;
- deliberation invariants.

It is a cross-cutting working model, not a maturity axis and not proof.

### Action Authorization Packet

Authoritative semantic contract:

- `ACTION_AUTHORIZATION_PACKET_v1.0.md`

Current authoritative status:

```text
CONTRACT: FROZEN
VALIDATOR: IMPLEMENTED ON MAIN
POSITIVE VALIDATION RESULT: READY_FOR_ATOMIC_CONSUMPTION
ATOMIC CONSUMPTION LEDGER: NOT CLAIMED ON MAIN
ACTION-RESULT BINDING: NOT CLAIMED ON MAIN
```

The dedicated AAP contract and merged PR #15 supersede older statements that described AAP as `CONTRACT NOT FROZEN / NOT IMPLEMENTED`.

A valid AAP is not proof that the action occurred.

### Technical PASS versus product acceptance

`PASS` may occur as the result of a test or as an internal technical run-state concept where specifically defined.

It never means, by itself:

```text
HUMAN ACCEPTED
PRODUCT ACCEPTED
MERGED
MATURITY LEVEL ACHIEVED
```

Product/maturity acceptance requires the exact evidence and human decision defined by the governing contract or maturity ladder.

### Golden Path 001

Product scenario definition:

- `docs/product/GOLDEN_PATH_001_FIX_FAILING_TEST.md`

Owns the first user-visible vertical scenario.

The future machine-readable GP001 contract may constrain execution further, but may not silently change the product promise or expand authority.

## 3. Status hierarchy

Always distinguish these questions:

```text
ARCHITECTURE
What belongs in the system?

IMPLEMENTATION
What exists on main?

BUILD PRIORITY
What do we build next?

MATURITY / PROOF
What have we proved?
```

A positive answer in one dimension is not a positive answer in another.

Examples:

```text
BUILD MAP: ACCEPTED
MATURITY: NONE
IMPLEMENTATION: NOT CLAIMED
```

and:

```text
AAP CONTRACT: FROZEN
AAP VALIDATOR: IMPLEMENTED
AAP ATOMIC LEDGER: NOT IMPLEMENTED ON MAIN
```

are both valid states.

## 4. Repository-state rule

Canonical runtime/document state comes from merged `main`.

The following are non-canonical until merged:

- draft PRs;
- open PRs;
- branch-only documents;
- review comments;
- generated candidate artifacts;
- proposed status text in a PR description.

They may contain valuable evidence or future decisions, but they do not silently override `main`.

This specifically means that the Product Contract carried by open draft PR #34 is not current canonical repository state.

## 5. README rule

`README.md` is a navigation and current-status summary.

It must point to authoritative sources but does not override them. If README conflicts with a dedicated authoritative contract, the dedicated contract wins and README must be corrected.

## 6. Naming rule: v1 versus maturity P-levels

`v1` in filenames such as `EXECUTOR_V1_PRODUCT_SPEC.md` identifies the version of that document/product slice.

It does not mean:

- `Executor 1.0` maturity;
- `P4 — REPEATABLE EXECUTOR 1.0`;
- production readiness.

Maturity is claimed only through `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` evidence gates.

## 7. Current baseline after PR #42

```text
ARCHITECTURE / PRODUCT BUILD BASELINE: ACCEPTED
MATURITY ADVANCEMENT FROM PR #42: NONE
RUNTIME IMPLEMENTATION CLAIM FROM PR #42: NONE
CURRENT BUILD TARGET: GP001 VERTICAL PRODUCT PATH
NEXT CHANGE: DOCUMENT AUTHORITY RECONCILIATION
```

After this reconciliation is accepted, the next critical-path artifact is the machine-readable GP001 contract.
