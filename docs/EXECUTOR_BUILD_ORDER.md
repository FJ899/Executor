---
document: "Executor Build Order"
version: "1.1"
status: "ACTIVE / CURRENT THROUGH REQUEST_TO_CONTRACT_001 PHASE 1"
date: "2026-08-09"
scope: "ordered path from first repeatable execution slice to governed request-to-contract product entry"
repository: "JTJ07/Executor"
---

# Executor Build Order v1.1

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
CURRENT PRODUCT GAP
     |
     v
MINIMAL PR
     |
     v
ATTACK / END-TO-END RESULT
     |
     v
PROOF / MATURITY ASSESSMENT
```

Failure-driven safety work attacks each relevant step but does not replace the product path.

## 2. Current product target

First user: software developer / engineer.

Current product promise:

> A user can express a bounded repository request in normal language; Executor System turns it into an explicit draft contract, requires authorization, executes only the frozen contract, and returns evidence for review.

First technical golden path remains:

> `GP001 — Fix a failing test.`

Current next product slice:

> `REQUEST_TO_CONTRACT_001 — form and authorize GP001 from a normal user request.`

## 3. Non-goals

Executor v1 does not attempt to:

- autonomously redefine user goals;
- treat AI interpretation as authoritative user intent;
- turn a request directly into execution authority;
- promote a draft contract without authorization;
- replace project authority;
- expand task scope without authorization;
- certify its own correctness;
- become a general autonomous agent.

These non-goals preserve the core boundaries:

```text
REQUEST != CONTRACT
AI INTERPRETATION != USER INTENT
DRAFT CONTRACT != AUTHORIZED CONTRACT
CONTRACT != RECOMMENDATION
CAPABILITY != AUTHORITY
EXECUTION != PROOF
```

## 4. Completed critical-path phases

### PHASE A — Product/build baseline

Accepted through PR #42.

### PHASE B — Document authority reconciliation

Accepted through PR #43.

### PHASE C — GP001 machine-readable contract

Accepted through PR #44.

### PHASE D — First vertical runtime slice and controlled authority

Accepted through PR #45.

### PHASE E — Adversarial GP001 attack

Accepted through PR #46.

Falsification history retained:

```text
F-1 caller-forged authority
F-2 implementation-level policy bypass
F-3 post-validation authority drift
```

### PHASE F — Real GP001 end-to-end execution

Accepted through PR #47.

Observed bounded terminal state:

```text
ACTION_COMPLETED_REVIEW_REQUIRED
human_decision_required: true
```

### PHASE G — GP001 repeatability / replay

Accepted through PR #48.

Observed replay gate:

```text
contractual_equivalence: EQUIVALENT
ephemeral_independence: DISTINCT
human_decision_required: true
```

The above phases establish one bounded repeatable execution slice. They do not establish a maturity or product-readiness claim.

## 5. Completed phase — governed request-to-contract formation

### PHASE H — REQUEST_TO_CONTRACT_001 / PHASE 1 ACCEPTED

Purpose:

> Prove that one normal human request can be converted into a truthful, bounded draft contract without silently manufacturing user intent or execution authority.

Use the existing GP001 problem so only the formation boundary changes.

Target path:

```text
USER REQUEST
      |
      v
INTERPRET
      |
      v
DRAFT TASK CONTRACT
      |
      v
CRITIQUE
      |
      v
HUMAN DECISION
  ACCEPT / MODIFY / REJECT
      |
      v
FROZEN TASK CONTRACT
      |
      v
EXISTING GP001 RUNTIME
```

### H1 — Authority baseline

Before formation code becomes critical-path implementation, canonical documentation must state:

```text
AI INTERPRETATION != USER INTENT
REQUEST != CONTRACT
DRAFT CONTRACT != AUTHORIZED CONTRACT
CONTRACT FORMATION IS A GOVERNED ACTION
```

### H2 — Formation contract/state model

Minimum non-executable states:

```text
REQUEST_RECEIVED
INTERPRETATION_PROPOSED
DRAFT_CONTRACT_CREATED
DRAFT_CRITIQUED
AWAITING_HUMAN_AUTHORIZATION
```

Only an explicit authority transition may create:

```text
AUTHORIZED_AND_FROZEN
```

### H3 — User/AI provenance

Formation output must distinguish:

- user-supplied facts;
- AI-inferred proposals;
- unresolved assumptions;
- discoveries kept out of scope.

### H4 — Draft critique

Before human authorization, critique must detect or report at least:

- silent scope expansion;
- unsupported repository/commit/target inference;
- weakened success conditions;
- discovered work added without authority.

Critique may recommend a correction. It may not authorize it.

### H5 — Human decision surface

Minimum user-facing draft:

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

Allowed decisions:

```text
ACCEPT
MODIFY
REJECT
```

### H6 — Semantic compatibility with GP001

The accepted formation output must freeze into a task contract semantically compatible with the existing GP001 runtime contract.

Do not modify GP001 execution authority, protected paths, success criteria or terminal semantics merely to make formation easier.

### H7 — Adversarial formation tests

Attack formation with examples such as:

- user asks for X; model adds Y;
- user names no repository; model invents one;
- model changes protected test scope;
- critique discovers Y and silently includes it;
- draft attempts to execute before authorization;
- modified/rejected draft remains executable;
- AI-generated `ACCEPT` is treated as human authorization.

Expected behavior is fail closed or visible `NEEDS_CLARIFICATION`, never silent authority expansion.

### H8 — First request-to-result E2E

Only after formation attacks pass:

```text
normal user request
  -> governed draft
  -> human authorization
  -> frozen GP001 contract
  -> existing GP001 execution
  -> ACTION_COMPLETED_REVIEW_REQUIRED
```

Phase 1 was accepted through PR #50. It preserves the verbatim request, separates model/process provenance, creates and critiques the exact canonical GP001 draft, and exports a hash-bound non-executable authorization request. It intentionally stops at `AWAITING_VERIFIED_HUMAN_AUTHORIZATION`.

## 6. Current phase — verified human authority boundary

Purpose:

> Allow an authenticated human decision bound to the exact current draft to create `AUTHORIZED_AND_FROZEN`, without accepting a caller-provided role string or self-declared identity as authority.

Required inputs before implementation:

- an explicitly selected request-origin / human-identity trust provider;
- evidence semantics for `ACCEPT`, `MODIFY` and `REJECT` bound to `draft_sha256`;
- freshness, replay and revocation rules;
- a negative-test plan proving that process-local or model-generated claims cannot cross the boundary.

Until those inputs are selected, the correct terminal result is:

```text
AWAITING_VERIFIED_HUMAN_AUTHORIZATION
executable: false
```

This is an authority/design decision, not a missing convenience method. The repository must not fabricate a generic identity provider to make the state transition green.

## 7. Work explicitly deferred

Until the verified-human-authority boundary needs them to remove a measured blocker:

- separate proposer/critic/researcher agent services;
- multi-agent orchestration;
- generalized natural-language contract generation;
- generalized deliberation runtime;
- long-term Executor-owned project memory;
- broad research capability;
- GP002 for breadth alone;
- marketplace;
- enterprise integrations;
- autonomous deployment;
- automatic contract authorization;
- cosmetic UI expansion.

## 8. Decision rule for every next PR

A PR enters the critical path only if all three are answerable:

1. Which current product blocker does it remove?
2. Which Build Map element owns it?
3. What observable evidence will show that the blocker is gone?

For formation work add a fourth question:

4. Could this change accidentally turn AI interpretation into authority?

If these answers are missing, the work is deferred or moved outside the critical path.

## 9. Immediate next artifact

The next critical-path artifact is:

> **A provider-specific verified-human-authority contract and adversarial evidence plan, selected explicitly before runtime implementation.**

Do not begin GP002, generalized task generation, multi-agent roles or broader capabilities before this boundary is demonstrated.
