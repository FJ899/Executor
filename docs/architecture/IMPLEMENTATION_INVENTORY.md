---
document: "Executor Implementation Inventory"
version: "0.2"
status: "PHASE B CANDIDATE / GITHUB TRUST AND BOUNDED PILOT RUNTIME"
date: "2026-08-09"
scope: "current implementation mapped to Executor Build Map and next product slice"
repository: "JTJ07/Executor"
baseline: "Phase B work branch from main@5e254811; no P4 or merge claim"
---

# Executor Implementation Inventory v0.2

## 1. Purpose

This inventory answers:

> What from the Build Map actually exists today, and what is the next missing product boundary?

It is not a maturity claim and does not promote any P-level.

## 2. Status vocabulary

- `EXISTS` — implemented on `main` in a meaningful bounded form;
- `PARTIAL` — some required behavior exists but the Build Map element is incomplete;
- `SKELETON` — structure exists without a usable bounded flow;
- `MISSING` — no implementation evidence found for the required product behavior;
- `LOCKED / LATER` — intentionally outside the current product slice;
- `OPEN DRAFT` — work exists outside accepted `main` and is not counted as canonical implementation.

## 3. Main-branch inventory

| Build Map element | Status | Current evidence | Product implication |
|---|---|---|---|
| F0 Request-to-Contract Boundary | IMPLEMENTED CANDIDATE | phase-1 formation plus GitHub issue/comment verification, exact draft binding and freeze exist with adversarial tests | Real direct-human events remain required |
| F1 Contract Interpretation Boundary | EXISTS (bounded) | GP001 machine-readable contract, contract validation and action-boundary revalidation are accepted on `main` | Kernel can execute a frozen bounded contract; it does not yet form one from user language |
| F2 Source & Workspace Access | EXISTS (bounded) | Controlled External Fixture authority pins exact repository + commit; real GP001 E2E acquired and checked exact source identity | Proven for one controlled fixture, not arbitrary repositories |
| F3 Execution State Model | IMPLEMENTED CANDIDATE | formation, GitHub decision, frozen contract, atomic authority and bound terminal pilot result remain distinct | Real pilot evidence pending |
| F4 Evidence Boundary | EXISTS (bounded) | GP001 real E2E records input identity, authority binding, pre/post test state, regression state, scope and review-required status | Evidence is usable for the bounded vertical slice; still not a general product/maturity claim |
| S0 Contract Formation Flow | IMPLEMENTED CANDIDATE | bounded formation and exact GitHub decision-to-freeze path exist | Direct-human GitHub events pending |
| S1 Runtime Engine | EXISTS (GP001 bounded) | accepted GP001 runtime performs pinned failure reproduction, authorized mutation, verification and report | First execution vertical slice exists |
| S2 Planning Layer | PARTIAL | GP001 E2E produces a deterministic bounded plan, but no general AI planning layer is claimed | Enough for GP001 execution; formation/planning must stay separate |
| S3 Action Execution Layer | EXISTS (GP001 bounded) | one exact `WRITE_REPOSITORY` mutation is policy/AAP bound and executed in sandbox | Proven only for the accepted fixture/action class |
| S4 Verification Loop | EXISTS (GP001 bounded) | target FAIL before, target PASS after, 13-test regression PASS, compileall PASS, exact scope and protected-material checks | First real verification loop exists |
| I1 Execution State & Working Memory | EXISTS (bounded) | run state, checkpoints, execution artifacts and replay observations exist | Do not add strategic/user-goal memory to Executor |
| I2 Context Management | PARTIAL | execution context is pinned and bounded; formation context does not yet distinguish user facts from AI inference in a runtime artifact | Request-to-contract must introduce provenance/assumption separation |
| I3 Tool Management | EXISTS (bounded) | policy, action authorization, exact fixture binding, no generic external-project capability | Preserve capability/authority separation during formation work |
| I4 Sandbox & Isolation | EXISTS (GP001 bounded) | real hosted-runner Docker execution, immutable image identity and cleanup checks passed | Proven for one bounded fixture |
| C1 Software Engineering Capability | PARTIAL / FIRST SLICE WORKS | GP001 real E2E and repeatability prove one failing-test repair path | Capability is real but still narrow and not user-accessible from natural language |
| C2 Analysis Capability | LOCKED / LATER | not required for current slice | Do not build now |
| C3 Research Capability | LOCKED / LATER | not required for `REQUEST_TO_CONTRACT_001` | Do not build unless a measured formation blocker requires it |
| C4 Operational Capability | LOCKED / LATER | not required for current slice | Defer |
| UX1 Request Surface | IMPLEMENTED CANDIDATE | CLI verifies a governed GitHub issue and emits an exact non-executable draft | Publish and observe real requests |
| UX2 Contract Decision Surface | IMPLEMENTED CANDIDATE | CLI consumes exact fresh GitHub `ACCEPT/MODIFY/REJECT`; only ACCEPT freezes | Publish and observe real decisions |
| UX3 Execution Interaction Model | PARTIAL | GP001 report is concise and review-oriented, but user does not yet enter through request formation | Reuse after contract authorization |
| UX4 Result Report | EXISTS (GP001 bounded) | real GP001 ends in `ACTION_COMPLETED_REVIEW_REQUIRED` with evidence and human decision required | Preserve terminal semantics |
| LEVEL 6 Extensions | LOCKED / LATER | multi-agent, marketplace, broad integrations not required | Explicitly defer |

## 4. Accepted vertical-slice evidence

The following sequence has been accepted on the product critical path:

```text
PRODUCT / BUILD BASELINE
      -> DOCUMENT AUTHORITY RECONCILIATION
      -> GP001 MACHINE-READABLE CONTRACT
      -> CONTROLLED EXTERNAL FIXTURE AUTHORITY
      -> FIRST VERTICAL RUNTIME SLICE
      -> ADVERSARIAL GP001 VALIDATION
      -> REAL GP001 E2E
      -> REPEATABILITY / REPLAY
```

Observed bounded result:

```text
exact input identity: MATCH
controlled fixture authority: BOUND
pre-change target test: FAIL
post-change target test: PASS
regression checks: PASS
scope: ALLOWED
protected material: UNCHANGED
terminal status: ACTION_COMPLETED_REVIEW_REQUIRED
human decision required: true
replay contractual equivalence: EQUIVALENT
replay ephemeral identity: DISTINCT
```

This establishes a repeatable bounded execution slice. It does not establish general product maturity.

## 5. Falsification history that now constrains implementation

### F-1 — Caller-forged authority

Closed by removing caller-owned authority context from the public GP001 path.

### F-2 — Implementation-level policy bypass

Closed by moving Controlled External Fixture authority into verified policy binding rather than runtime hard-code.

### F-3 — Post-validation authority drift

Closed by revalidating frozen contract-derived authority-critical state before consequential actions.

Formation work must preserve the same discipline:

> A generated interpretation or draft must not become authority merely because it exists in memory or was produced by an AI component.

## 6. Current primary product gap

The largest remaining gap is external proof:

```text
DIRECT-HUMAN GITHUB REQUEST
  -> EXACT DRAFT
  -> DIRECT-HUMAN GITHUB ACCEPT
  -> FROZEN PILOT CONTRACT
  -> EXTERNAL SOLUTION PROPOSAL
  -> ATOMIC AAP + BOUNDED PILOT RUNTIME
  -> TWO REAL DRAFT PRS
  -> INDEPENDENT PHASE C
```

This is the boundary between ordinary AI assistance and governed execution.

## 7. Immediate implementation targets

### GAP-008 — Governed contract formation

Implement formation states that cannot directly execute:

```text
REQUEST_RECEIVED
INTERPRETATION_PROPOSED
DRAFT_CONTRACT_CREATED
DRAFT_CRITIQUED
AWAITING_HUMAN_AUTHORIZATION
```

Only an explicit authorization transition may create `AUTHORIZED_AND_FROZEN`.

### GAP-009 — User/AI provenance

The draft must distinguish at least:

- what the user actually supplied;
- what the system inferred;
- what remains unresolved;
- what was discovered but remains out of scope.

### GAP-010 — Contract critique

Before authorization, detect/report:

- silent scope expansion;
- unsupported target/repository/commit inference;
- weakened success criteria;
- hidden out-of-scope work.

Critique cannot authorize its own correction.

### GAP-011 — Human contract decision surface

Expose:

```text
ACCEPT
MODIFY
REJECT
```

and ensure a draft remains non-executable until `ACCEPT` or an equivalent superior-authority action.

### GAP-012 — GP001 semantic compatibility

The first authorized formation output must freeze into a task contract semantically compatible with the already accepted GP001 contract/runtime, without changing GP001's execution authority or success criteria.

## 8. Stop rule

Until `REQUEST_TO_CONTRACT_001` is proven end to end, do not implement:

- generalized natural-language contract generation;
- separate multi-agent services;
- autonomous contract authorization;
- long-term Executor-owned project memory;
- GP002 merely to add breadth;
- generalized research capability;
- marketplace;
- enterprise integrations;
- autonomous deployment.

The next product question is not whether Executor can do more.

It is:

> Can Executor translate one bounded human request into a truthful draft, keep interpretation separate from authority, obtain human authorization, and hand the frozen contract to the already proven execution kernel?
