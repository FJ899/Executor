---
document: "Contract Formation Boundary"
version: "1.0"
status: "USER DIRECTION ACCEPTED / CANDIDATE BASELINE"
date: "2026-08-09"
scope: "governed translation from human request to authorized task contract"
repository: "JTJ07/Executor"
---

# Contract Formation Boundary v1

## 1. Purpose

This document defines the boundary between a human request and an executable task contract.

The core rule is:

> **CONTRACT FORMATION IS A GOVERNED ACTION.**

Turning natural language into executable authority is not a formatting step. It is the point where interpretation can begin to affect the real action space of the system.

## 2. Distinct objects

The following are not interchangeable:

```text
USER REQUEST
    !=
AI INTERPRETATION
    !=
DRAFT TASK CONTRACT
    !=
AUTHORIZED / FROZEN TASK CONTRACT
```

### User Request

Natural-language expression supplied by the user, for example:

```text
Fix the failing test about batch atomicity.
```

It is evidence of user intent, but it is not itself a complete executable contract.

### AI Interpretation

A structured hypothesis about what the request means.

Interpretation may infer candidate targets, scope, success conditions and unresolved questions, but inference is not user intent and does not create authority.

### Draft Task Contract

A proposed executable boundary containing explicit fields such as:

- objective;
- repository and pinned input identity;
- target test or acceptance condition;
- proposed write scope;
- protected material;
- required verification;
- forbidden actions;
- discoveries outside scope;
- unresolved assumptions.

A draft is review material. It is not executable authority.

### Authorized / Frozen Task Contract

A draft that has passed the required human or superior-authority decision gate and has been frozen for execution.

Only this state may enter the Executor execution kernel.

## 3. Contract formation pipeline

```text
USER REQUEST
      |
      v
INTERPRET
      |
      v
PROPOSE DRAFT CONTRACT
      |
      v
CRITIQUE
      |
      v
PRESENT DECISION SURFACE
      |
      v
HUMAN AUTHORIZATION
   /          |          \
ACCEPT      MODIFY      REJECT
   |
   v
FROZEN TASK CONTRACT
   |
   v
EXECUTION KERNEL
```

The first implementation may use one model/process for `INTERPRET -> PROPOSE -> CRITIQUE`. Architectural roles do not require separate agents.

## 4. Formation invariants

### CFI-001 — REQUEST != CONTRACT

A natural-language request must not be treated as a complete executable contract merely because a model can infer missing details.

### CFI-002 — AI INTERPRETATION != USER INTENT

Model interpretation is a proposal about meaning, not authoritative evidence that the user intended every inferred detail.

### CFI-003 — DRAFT CONTRACT != AUTHORIZED CONTRACT

A generated contract remains non-executable until the required authorization gate has accepted it.

### CFI-004 — CONTRACT FORMATION IS A GOVERNED ACTION

Any transition that changes a request into executable authority must be observable, reviewable and constrained by a defined authorization boundary.

### CFI-005 — DISCOVERY MAY NOT SILENTLY EXPAND THE CONTRACT

If interpretation or critique discovers an additional problem, opportunity or broader architectural concern, it must remain outside the current contract unless separately authorized.

Correct behavior:

```text
CURRENT CONTRACT:
X

DISCOVERY:
Y

ACTION ON Y:
NONE

RECOMMENDATION:
Create or authorize a separate contract.
```

Incorrect behavior:

```text
UPDATED CONTRACT:
X + Y
```

without an explicit authority transition.

## 5. Formation state model

Minimum states:

```text
REQUEST_RECEIVED
      -> INTERPRETATION_PROPOSED
      -> DRAFT_CONTRACT_CREATED
      -> DRAFT_CRITIQUED
      -> AWAITING_HUMAN_AUTHORIZATION
      -> AUTHORIZED_AND_FROZEN
```

Alternative terminal/non-executable states:

```text
NEEDS_CLARIFICATION
REJECTED
CANCELLED
```

No execution transition is legal from:

```text
REQUEST_RECEIVED
INTERPRETATION_PROPOSED
DRAFT_CONTRACT_CREATED
DRAFT_CRITIQUED
AWAITING_HUMAN_AUTHORIZATION
```

## 6. Human decision surface

The user should not need to inspect internal prompts or model transcripts.

Minimum decision surface:

```text
REQUEST
UNDERSTOOD OBJECTIVE
TARGET / INPUT IDENTITY
PROPOSED WRITE SCOPE
PROTECTED MATERIAL
SUCCESS CONDITIONS
DISCOVERED BUT OUT OF SCOPE
UNRESOLVED ASSUMPTIONS
STATUS: DRAFT — USER AUTHORIZATION REQUIRED
```

The user must be able to accept, modify or reject the draft.

## 7. REQUEST_TO_CONTRACT_001 scope

The first formation slice is intentionally narrow.

It will reuse GP001 rather than introduce a new technical problem.

Target request class:

> A user asks to fix the known GP001 failing test without manually authoring `task.yaml`.

The slice must prove only that the system can:

1. receive a bounded natural-language request;
2. form a truthful GP001 draft contract;
3. expose assumptions and out-of-scope discoveries;
4. critique the draft for scope expansion or unsupported inference;
5. require human authorization;
6. freeze an authorized contract that is semantically compatible with the existing GP001 execution contract.

It does not need to prove general natural-language understanding, arbitrary project contract generation, multiple autonomous agents, long-term memory, or automatic authorization.

## 8. Relationship to execution

Contract formation owns the transition from request to proposed authority.

The execution kernel owns only execution of an already authorized contract.

```text
FORMATION LAYER
What exactly is being proposed for authorization?
        |
        v
HUMAN / SUPERIOR AUTHORITY
Is this the action I authorize?
        |
        v
EXECUTION KERNEL
Can this frozen contract be executed within policy?
        |
        v
VERIFICATION
What actually happened?
```

No layer may silently absorb the authority of its neighbor.
