---
document: "Contract Formation Boundary"
version: "1.1"
status: "OWNERSHIP RECONCILIATION CANDIDATE / DIRECTION AUTHORIZED"
date: "2026-08-19"
scope: "governed materialization and binding of proposed meaning into an authorized task contract"
repository: "JTJ07/Executor"
---

# Contract Formation Boundary v1.1

## 1. Purpose

This document defines the boundary between a Human request, Intelligence-produced interpretation/HOW proposals, and an executable task contract.

The core rule is:

> **CONTRACT FORMATION IS A GOVERNED MATERIALIZATION AND BINDING ACTION, NOT THE OWNER OF OPERATIONAL HOW.**

Turning proposed meaning into executable authority is not a formatting step. It is the point where a proposal can begin to constrain the real action space of the system. Contract Formation must therefore preserve provenance, expose unresolved meaning, reject scope drift and require Human/superior authority before any draft becomes executable.

Semantic ownership remains separate:

```text
HUMAN
  owns intent / goal / DONE / normative decisions

EXTERNAL / BASE INTELLIGENCE
  interprets the problem space and proposes/selects operational HOW

CONTRACT FORMATION
  materializes and binds supplied/accepted meaning and scope
  into a reviewable bounded contract representation

EXECUTOR
  executes only an already authorized/frozen consequential contract

VERIFIER
  independently establishes facts
```

Capability to interpret text inside one process does not transfer semantic ownership of HOW into Contract Formation.

## 2. Distinct objects

The following are not interchangeable:

```text
USER REQUEST
    !=
INTELLIGENCE INTERPRETATION / HOW PROPOSAL
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

### Intelligence Interpretation / HOW Proposal

A structured proposal about what the request means and how the bounded problem could be solved.

Intelligence may infer candidate targets, scope, success conditions and unresolved questions. Those inferences are proposals, not authoritative user intent, Human decisions or effect authority.

### Draft Task Contract

A reviewable materialization of proposed/accepted meaning containing explicit fields such as:

- objective;
- repository and pinned input identity;
- target test or acceptance condition;
- proposed write scope;
- protected material;
- required verification;
- forbidden actions;
- discoveries outside scope;
- unresolved assumptions.

A draft is review material. It is not executable authority and its existence does not prove that its semantics were Human-authorized.

### Authorized / Frozen Task Contract

A draft that has passed the required Human or superior-authority decision gate and has been frozen for execution.

Only this state may enter the Executor execution kernel.

## 3. Contract formation pipeline

The semantic pipeline is:

```text
USER REQUEST / ACCEPTED MEANING
      |
      v
EXTERNAL / BASE INTELLIGENCE
 interpret problem / propose HOW and candidate contract meaning
      |
      v
CONTRACT FORMATION
 materialize / bind / provenance-check / critique for drift
      |
      v
DRAFT TASK CONTRACT
      |
      v
PRESENT DECISION SURFACE
      |
      v
HUMAN / SUPERIOR AUTHORIZATION
   /          |          \
ACCEPT      MODIFY      REJECT
   |
   v
FROZEN TASK CONTRACT
      |
      v
EXECUTION KERNEL
```

The same model or process may technically perform more than one step. That implementation convenience does not merge semantic ownership. In particular, a Contract Formation API may accept fields named `understood_objective` or `proposed_task_contract`, but the proposal remains Intelligence provenance and Contract Formation does not gain ownership of selecting HOW by storing, checking or critiquing it.

## 4. Formation invariants

### CFI-001 — REQUEST != CONTRACT

A natural-language request must not be treated as a complete executable contract merely because a model can infer missing details.

### CFI-002 — INTELLIGENCE INTERPRETATION != USER INTENT

Model/Intelligence interpretation is a proposal about meaning, not authoritative evidence that the user intended every inferred detail.

### CFI-003 — DRAFT CONTRACT != AUTHORIZED CONTRACT

A generated/materialized contract remains non-executable until the required authorization gate has accepted it.

### CFI-004 — CONTRACT FORMATION IS A GOVERNED BINDING ACTION

Any transition that materializes proposed meaning into a candidate executable boundary must be observable, reviewable, provenance-bound and constrained by a defined authorization boundary.

This governance responsibility does not grant Contract Formation semantic ownership of the proposal it materializes.

### CFI-005 — DISCOVERY MAY NOT SILENTLY EXPAND THE CONTRACT

If Intelligence, formation-time critique or validation discovers an additional problem, opportunity or broader architectural concern, it must remain outside the current contract unless separately authorized.

Correct behavior:

```text
CURRENT CONTRACT:
X

DISCOVERY:
Y

ACTION ON Y:
NONE

RECOMMENDATION:
Return Y to Intelligence/Human decision space or create a separately authorized contract.
```

Incorrect behavior:

```text
UPDATED CONTRACT:
X + Y
```

without an explicit authority transition.

### CFI-006 — CONTRACT FORMATION MUST NOT SELECT HOW

Contract Formation may validate structure, provenance, scope compatibility, unresolved assumptions and divergence from an accepted profile. It must not originate, rank, select, route or optimize the operational solution merely because it is capable of generating text.

If a different HOW is needed, that question returns to Intelligence and, where normative meaning changes, to the Human.

## 5. Formation state model

Minimum materialization states:

```text
REQUEST / PROPOSAL RECEIVED
      -> PROPOSAL BOUND
      -> DRAFT_CONTRACT_CREATED
      -> DRAFT_CRITIQUED
      -> AWAITING_HUMAN_AUTHORIZATION
      -> AUTHORIZED_AND_FROZEN
```

An implementation may preserve historical names such as `REQUEST_RECEIVED` or `INTERPRETATION_PROPOSED`. Those names describe local processing state; they do not assign semantic ownership of interpretation/HOW to Contract Formation.

Alternative terminal/non-executable states:

```text
NEEDS_CLARIFICATION
REJECTED
CANCELLED
```

No execution transition is legal from any non-authorized formation state.

## 6. Human decision surface

The user should not need to inspect internal prompts or model transcripts.

Minimum decision surface:

```text
REQUEST
PROPOSED / UNDERSTOOD OBJECTIVE
TARGET / INPUT IDENTITY
PROPOSED WRITE SCOPE
PROTECTED MATERIAL
SUCCESS CONDITIONS
DISCOVERED BUT OUT OF SCOPE
UNRESOLVED ASSUMPTIONS
PROVENANCE OF PROPOSED MEANING
STATUS: DRAFT — USER AUTHORIZATION REQUIRED
```

The user must be able to accept, modify or reject the draft. Human authorization accepts the bounded semantics presented; it does not retroactively convert every prior AI inference into Human-authored meaning.

## 7. REQUEST_TO_CONTRACT_001 scope

The first formation slice remains intentionally narrow.

It reuses GP001 rather than introducing a new technical problem.

Target request class:

> A user asks to fix the known GP001 failing test without manually authoring `task.yaml`.

The implemented slice proves only that the system can:

1. receive a bounded natural-language request;
2. accept an Intelligence/model proposal for the GP001 interpretation and task contract;
3. materialize that proposal with truthful provenance;
4. expose assumptions and out-of-scope discoveries;
5. critique the draft for scope expansion, unsupported inference or divergence from the accepted GP001 profile;
6. require verified Human authorization before executable authority can exist.

The current `RequestToContract001` implementation deliberately records structured extraction/proposed objective as `MODEL` provenance and blocks contract divergence from the accepted GP001 profile. It does not prove general natural-language understanding, arbitrary project contract generation, autonomous HOW ownership, multiple autonomous agents, long-term memory or automatic authorization.

## 8. Relationship to Intelligence and execution

The boundary is:

```text
INTELLIGENCE
What HOW / bounded meaning is being proposed, and why?
        |
        v
CONTRACT FORMATION
Can that supplied proposal be truthfully materialized and bound
without adding meaning, scope or authority?
        |
        v
HUMAN / SUPERIOR AUTHORITY
Is this the bounded action I authorize?
        |
        v
EXECUTION KERNEL
Can this frozen contract be executed within policy?
        |
        v
VERIFICATION
What actually happened?
```

Contract Formation owns the integrity of materialization/binding and the non-executable draft-to-authorized boundary. It does **not** own the Human goal, normative meaning, operational HOW or effect authority.

No layer may silently absorb the semantic ownership or authority of its neighbor.

## 9. Reconciliation note

This v1.1 wording reconciles the earlier local phrase `Contract formation owns the transition from request to proposed authority` with the later accepted ecosystem ownership model.

It does not change Executor runtime behavior, the accepted Executor 1.0 product state, the GP001 implementation, Human authority requirements, release/deploy state or any capability. It removes only the architectural ambiguity that could otherwise allow Contract Formation to be misread as the owner of Intelligence's HOW-selection function.
