---
document: "Executor Build Order"
version: "1.0"
status: "PROPOSED EXECUTION ORDER / PENDING REPO MERGE"
date: "2026-08-08"
scope: "ordered path from architecture baseline to first proven product slice"
repository: "litrgratis-pixel/Executor"
---

# Executor Build Order v1

## 1. Goal

Stop selecting work from whichever technical problem is currently most interesting.

Use this cycle:

```text
PRODUCT SPEC
     |
     v
BUILD MAP
     |
     v
IMPLEMENTATION INVENTORY
     |
     v
GAP
     |
     v
MINIMAL PR
     |
     v
END-TO-END RESULT
     |
     v
PROOF / MATURITY ASSESSMENT
```

Failure-driven safety work attacks each relevant step but does not replace the product path.

## 2. Current product target

First user: software developer / engineer.

First promise:

> Safely perform a well-defined repository task and show what changed and whether it works.

First golden path:

> `GP001 — Fix a failing test.`

## 3. Non-goals

Executor v1 does not attempt to:

- autonomously redefine user goals;
- replace project authority;
- expand task scope without authorization;
- certify its own correctness;
- become a general autonomous agent.

These non-goals preserve the core boundaries:

```text
CONTRACT != RECOMMENDATION
CAPABILITY != AUTHORITY
EXECUTION != PROOF
```

## 4. Ordered work

### PHASE A — Freeze the product/build baseline

Current branch scope:

1. `docs/product/EXECUTOR_V1_PRODUCT_SPEC.md`
2. `docs/architecture/EXECUTOR_BUILD_MAP.md`
3. `docs/philosophy/HUMAN_AI_DELIBERATION_MODEL.md`
4. `docs/architecture/IMPLEMENTATION_INVENTORY.md`
5. `docs/product/GOLDEN_PATH_001_FIX_FAILING_TEST.md`
6. `docs/safety/AI_FAILURE_ATLAS.md`
7. this build-order document

Exit condition:

```text
HUMAN REVIEW: ACCEPTED
RUNTIME CHANGE: NONE
MATURITY CLAIM: NONE
```

### PHASE B — Reconcile canonical documentation

Create a separate documentation/governance PR that resolves known semantic conflicts without changing runtime.

Minimum targets:

- AAP freeze status conflict;
- relationship of open PR #34 Product Contract to the new product slice;
- technical `PASS` terminology versus Executor product status;
- `v1` product-slice naming versus `P4 — REPEATABLE EXECUTOR 1.0` terminology.

Exit condition:

> One readable authority chain with no contradictory status claims for the current build path.

### PHASE C — Freeze GP001 machine-readable contract

Define one bounded failing-test scenario with:

- pinned repository/source identity;
- reproducible pre-change failure;
- allowed code paths;
- protected acceptance material;
- required regression command;
- bounded retries/time/actions;
- terminal statuses;
- evidence requirements.

Do not write the solution into the contract.

Exit condition:

> An implementation can attempt GP001 without guessing scope or success criteria.

### PHASE D — Build the smallest vertical product slice

Implement only missing glue required for:

```text
start task
  -> acquire/read pinned repo
  -> reproduce failure
  -> analyze
  -> produce bounded plan
  -> authorization gate
  -> edit allowed code
  -> run target test
  -> run regressions
  -> scope/test-integrity verification
  -> concise report
```

Reuse existing contract, state, policy, sandbox and evidence components where they fit. Do not rewrite strong foundations merely to match new names.

Each PR must name:

```text
BUILD MAP TARGET:
MATURITY TARGET:
CURRENT GAP:
CHANGE:
PROOF:
NON-GOALS:
```

### PHASE E — Attack GP001 with relevant failure classes

Critical Failure Atlas cases for the first slice:

- FAI-001 Scope Expansion;
- FAI-002 Capability Abuse;
- FAI-004 Self Validation;
- FAI-006 Role Collapse where applicable;
- FAI-007 Acceptance Bypass.

FAI-003 credential misuse becomes critical only if GP001 receives credentials capable of side effects beyond the source/workspace boundary.

FAI-005 consensus illusion is not a blocker until deliberation/multiple model roles influence authoritative outcome.

Exit condition:

> Known GP001 false-success paths fail closed within the declared threat model.

### PHASE F — Run the first end-to-end product proof

Use a real bounded task consistent with the maturity ladder.

Measure:

- failure reproduced before change;
- solution produced without human code-writing;
- target test result;
- regression result;
- scope integrity;
- evidence completeness;
- human review time;
- execution time/cost;
- whether review was cheaper than manual implementation.

Exit condition:

> We can answer whether GP001 is genuinely useful, not merely technically runnable.

### PHASE G — Assess maturity after the run

Only after the product run:

- map evidence to `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`;
- declare `ACCEPT`, `REWORK`, `STOP`, or the exact existing ladder status supported by evidence;
- do not invent a new maturity level to reward implementation effort.

## 5. Work explicitly deferred

Until GP001 needs them to remove a measured blocker:

- multi-agent orchestration;
- generalized deliberation runtime;
- long-term Executor-owned project memory;
- research capability;
- marketplace;
- enterprise integrations;
- autonomous deployment;
- broad task-class support;
- cosmetic UI expansion.

## 6. Decision rule for every next PR

A PR enters the critical path only if all three are answerable:

1. Which GP001 or product blocker does it remove?
2. Which Build Map element owns it?
3. What observable evidence will show that the blocker is gone?

If those answers are missing, the work is deferred or moved outside the critical path.

## 7. Immediate next PR after this baseline

Recommended next change:

> **Documentation consistency and authority reconciliation.**

Reason: GP001 should not be encoded while repo documents disagree on contract/AAP status and while PR #34 contains a newer unmerged product contract that overlaps the newly agreed product boundary.

After that reconciliation, freeze the GP001 machine-readable contract and begin the first runtime vertical-slice PR.
