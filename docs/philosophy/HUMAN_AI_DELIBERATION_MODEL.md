---
document: "Human-AI Deliberation Model"
version: "1.0"
status: "USER APPROVED CONCEPT / PENDING REPO MERGE"
date: "2026-08-08"
scope: "cross-cutting responsibility model for proposal, challenge, synthesis, authorization, execution and proof"
repository: "litrgratis-pixel/Executor"
---

# Human-AI Deliberation Model v1

## 1. Purpose

This document defines how AI may improve the quality of a solution without becoming the owner of the goal, authorization, or proof.

It is a cross-cutting architectural pattern. It is not an additional product-maturity axis and it does not require a multi-agent implementation.

Core principle:

> Intelligence may be distributed. Responsibility must remain assigned.

## 2. Responsibility pipeline

```text
HUMAN AUTHORITY
      |
      v
CONTRACT BOUNDARY
      |
      v
DELIBERATION
 proposal / challenge / research / synthesis
      |
      v
RECOMMENDED PLAN
      |
      v
AUTHORIZATION
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

The deliberation mechanism may be implemented by one model taking separated roles, several model calls, several models, or another process. Architectural role separation does not imply separate agents or processes.

## 3. Deliberation roles

### Proposer

Question:

> How could the contract be executed?

Produces candidate plans and solutions.

### Critic

Question:

> What assumptions, risks, contradictions or failure modes are present in the proposal?

Improves the quality of thinking. The critic is not the authoritative verifier of executed reality.

### Researcher

Question:

> What relevant alternatives, facts or constraints are missing?

Expands the considered solution space without expanding execution authority.

### Synthesizer

Question:

> What plan should we recommend after considering proposals, challenges and evidence?

The synthesizer recommends. It does not authorize.

## 4. Authorization boundary

The following are distinct:

```text
RECOMMENDATION
      !=
AUTHORIZATION
```

Authorization comes from the human, an already approved contract, or another explicitly superior authority defined by the system.

When deliberation discovers a valuable action outside the current contract, the correct behavior is:

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

## 5. Proof boundary

Deliberation improves decisions. It does not prove execution facts.

The authoritative verifier asks:

> Do independently observable facts satisfy the contract?

It does not ask:

> Does Executor believe it succeeded?

Model agreement, self-critique, confidence, narrative quality, or a generated `PASS` are not substitutes for authoritative evidence.

## 6. Human-AI deliberation invariants

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

## 7. Non-goals

This model does not claim that:

- more agents automatically produce better answers;
- AI debate is proof;
- every role needs a separate model;
- every plan requires many deliberation rounds;
- human review can be replaced by model consensus;
- deliberation may change project canon or strategic goals;
- Executor should become a general autonomous decision maker.

## 8. UX consequence

The user should not need to read the complete internal deliberation transcript.

A useful decision interface exposes only the decision-relevant summary:

```text
RECOMMENDATION
CHALLENGES FOUND
CORRECTIONS APPLIED
UNRESOLVED QUESTIONS
OUT-OF-CONTRACT DISCOVERIES
HUMAN DECISION REQUIRED
```

The system may perform many internal reasoning passes while keeping the user's decision surface short.

## 9. Relationship to the ecosystem

A clean responsibility chain is:

```text
GINSENG   -> what should be considered?
COS       -> what is accepted as canon?
CONTRACT  -> what is authorized now?
EXECUTOR  -> can the authorized task be executed?
VERIFIER  -> can the execution result be proven?
HUMAN     -> what is accepted and what happens next?
```

No layer should silently absorb the authority of its neighbor.
