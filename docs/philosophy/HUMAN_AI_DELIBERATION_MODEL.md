---
document: "Human-AI Deliberation Model"
version: "1.1"
status: "USER ACCEPTED / ACTIVE BASELINE"
date: "2026-08-09"
scope: "cross-cutting responsibility model for contract formation, proposal, challenge, synthesis, authorization, execution and proof"
repository: "litrgratis-pixel/Executor"
---

# Human-AI Deliberation Model v1.1

## 1. Purpose

This document defines how AI may improve the quality of contract formation and execution planning without becoming the owner of the goal, authorization, or proof.

It is a cross-cutting architectural pattern. It is not an additional product-maturity axis and it does not require a multi-agent implementation.

Core principle:

> Intelligence may be distributed. Responsibility must remain assigned.

## 2. Responsibility pipeline

Executor System contains two different deliberation contexts that must not be collapsed.

### Contract-formation deliberation

```text
HUMAN REQUEST
      |
      v
INTERPRET / PROPOSE / CRITIQUE
      |
      v
DRAFT TASK CONTRACT
      |
      v
HUMAN AUTHORIZATION
      |
      v
FROZEN TASK CONTRACT
```

Its question is:

> What explicit action boundary should be presented to the human for authorization?

It may propose meaning. It may not manufacture user intent or execution authority.

### Execution deliberation

```text
FROZEN TASK CONTRACT
      |
      v
DELIBERATION
 proposal / challenge / research / synthesis
      |
      v
RECOMMENDED PLAN
      |
      v
ACTION AUTHORIZATION
      |
      v
EXECUTION
      |
      v
OBSERVATION / EVIDENCE
      |
      v
INDEPENDENT VERIFICATION
      |
      v
HUMAN DECISION
```

Its question is:

> How should the already authorized contract be executed?

The deliberation mechanisms may be implemented by one model taking separated roles, several model calls, several models, or another process. Architectural role separation does not imply separate agents or processes.

## 3. Deliberation roles

### Interpreter

Question:

> What does the request appear to ask for, and what remains uncertain?

Produces a structured interpretation. The interpretation is not authoritative user intent.

### Proposer

During formation:

> What explicit draft contract could represent the request?

During execution:

> How could the frozen contract be executed?

Produces candidate contracts or plans within the authority of the current stage.

### Critic

Question:

> What assumptions, scope expansions, contradictions, risks or failure modes are present in the proposal?

Improves the quality of thinking. The critic is not the authoritative verifier of executed reality and does not authorize the proposal it critiques.

### Researcher

Question:

> What relevant alternatives, facts or constraints are missing?

Expands the considered solution space without expanding execution authority.

### Synthesizer

Question:

> What contract or plan should we recommend after considering proposals, challenges and evidence?

The synthesizer recommends. It does not authorize.

## 4. Contract formation boundary

The following are distinct:

```text
REQUEST
  !=
AI INTERPRETATION
  !=
DRAFT CONTRACT
  !=
AUTHORIZED CONTRACT
```

Contract formation is itself a governed action because it converts ambiguous language into a proposed real-world action boundary.

The authoritative formation rules are defined in:

`docs/governance/CONTRACT_FORMATION_BOUNDARY.md`

When formation discovers an additional valuable action outside the user's request, the correct behavior is:

```text
CURRENT DRAFT:
Keep the requested objective bounded.

DISCOVERY:
Describe the additional issue or opportunity.

RECOMMENDATION:
Propose a separate contract or explicit expansion decision.

AUTHORITY:
Do not add it to the executable contract without authorization.
```

## 5. Execution authorization boundary

The following are distinct:

```text
RECOMMENDATION
      !=
AUTHORIZATION
```

Authorization comes from the human, an already approved contract, or another explicitly superior authority defined by the system.

When execution deliberation discovers a valuable action outside the current contract, the correct behavior is:

```text
DISCOVERY:
Describe the out-of-contract issue or opportunity.

IMPACT:
Explain why it matters.

RECOMMENDATION:
Propose a separate contract or human decision.

CURRENT EXECUTION:
Remain inside the current authorized scope.
```

## 6. Proof boundary

Deliberation improves decisions. It does not prove execution facts.

The authoritative verifier asks:

> Do independently observable facts satisfy the contract?

It does not ask:

> Does Executor believe it succeeded?

Model agreement, self-critique, confidence, narrative quality, or a generated `PASS` are not substitutes for authoritative evidence.

## 7. Human-AI deliberation invariants

### HDI-001 — AI AGREEMENT != PROOF

Agreement between one or many AI perspectives does not constitute proof of truth or successful execution.

### HDI-002 — CRITIC != VERIFIER

The critic challenges reasoning. The verifier establishes facts against acceptance requirements.

### HDI-003 — SYNTHESIS != AUTHORIZATION

Synthesis produces a recommendation. It does not grant authority to execute.

### HDI-004 — EXECUTION RESULT != ACCEPTED EVIDENCE

Executor may report what it did. Authoritative acceptance requires evidence under the defined trust boundary.

### HDI-005 — DELIBERATION MAY NOT EXPAND THE CONTRACT

New discoveries may be reported and recommended, but may not silently expand execution scope.

### HDI-006 — CAPABILITY != AUTHORITY

The technical ability to perform an action does not imply permission to perform that action.

### HDI-007 — POSSESSION OF CREDENTIAL != AUTHORITY

Discovering or receiving a credential does not itself authorize any action available through that credential.

### HDI-008 — AUTHORITY MUST NOT EXIST ONLY AS MODEL INSTRUCTION

High-impact boundaries must be enforceable outside model reasoning where practical. A natural-language instruction such as "do not touch production" is not equivalent to a hard permission boundary.

### HDI-009 — AI INTERPRETATION != USER INTENT

A model's interpretation of a request is a hypothesis about meaning, not proof that every inferred field or consequence was intended by the user.

### HDI-010 — REQUEST != CONTRACT

A natural-language request is not automatically an executable task contract.

### HDI-011 — DRAFT CONTRACT != AUTHORIZED CONTRACT

A generated draft is non-executable until the required authority explicitly accepts it.

### HDI-012 — CONTRACT FORMATION IS A GOVERNED ACTION

The transition from request to executable authority must be observable, reviewable and constrained. Contract generation may not silently create its own authority.

## 8. Non-goals

This model does not claim that:

- more agents automatically produce better answers;
- AI debate is proof;
- every role needs a separate model;
- every plan requires many deliberation rounds;
- human review can be replaced by model consensus;
- a model may infer missing execution authority from convenience or context;
- deliberation may change project canon or strategic goals;
- Executor should become a general autonomous decision maker.

## 9. UX consequence

The user should not need to read complete internal prompts or deliberation transcripts.

For contract formation, the useful decision surface is:

```text
REQUEST
UNDERSTOOD OBJECTIVE
TARGET / INPUT IDENTITY
PROPOSED SCOPE
SUCCESS CONDITIONS
DISCOVERED BUT OUT OF SCOPE
UNRESOLVED ASSUMPTIONS
STATUS: DRAFT — USER AUTHORIZATION REQUIRED
```

For execution, the useful decision surface is:

```text
RECOMMENDATION
CHALLENGES FOUND
CORRECTIONS APPLIED
UNRESOLVED QUESTIONS
OUT-OF-CONTRACT DISCOVERIES
HUMAN DECISION REQUIRED
```

The system may perform many internal reasoning passes while keeping the user's decision surface short.

## 10. Relationship to the ecosystem

A clean responsibility chain is:

```text
HUMAN REQUEST -> what does the human ask for?
FORMATION     -> what explicit action is proposed for authorization?
HUMAN         -> is that contract authorized?
GINSENG       -> what should be considered at the decision-intelligence layer?
COS           -> what is accepted as project canon?
CONTRACT      -> what is authorized now?
EXECUTOR      -> can the authorized task be executed?
VERIFIER      -> can the execution result be proven?
HUMAN         -> what is accepted and what happens next?
```

No layer should silently absorb the authority of its neighbor.
