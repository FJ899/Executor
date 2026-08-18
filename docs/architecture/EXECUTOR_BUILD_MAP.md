---
document: "Executor Build Map"
version: "1.1"
status: "USER ACCEPTED DIRECTION / ACTIVE BASELINE CANDIDATE"
date: "2026-08-09"
scope: "canonical architectural decomposition of Executor System"
repository: "JTJ07/Executor"
---

# Executor Build Map v1.1

## 1. Purpose

This map answers:

> What are we actually building?

It is an architecture map, not a maturity certificate and not an implementation inventory.

Three separate questions remain separate:

- **Build Map** — what belongs to the system;
- **Implementation Inventory** — what currently exists;
- **Maturity / Proof Ladder** — what has been proven.

`HUMAN_AI_DELIBERATION_MODEL.md` is a cross-cutting way of working and is not a separate maturity axis.

## LEVEL 0 — PRODUCT DEFINITION

Executor is a system. The execution kernel is one component of that system.

```text
HUMAN REQUEST
      |
      v
CONTRACT FORMATION
 interpret / propose / critique
      |
      v
DRAFT TASK CONTRACT
      |
      v
HUMAN AUTHORIZATION
      |
      v
FROZEN TASK CONTRACT
      |
      v
EXECUTOR KERNEL
      |
      +--> plans execution
      +--> executes
      +--> observes
      +--> verifies technical result
      +--> reports
```

Core definition:

> Executor System turns a human request into an explicit, reviewable contract proposal, requires authority before that proposal becomes executable, then executes the frozen contract within policy and produces observable evidence for review.

Executor does not:

- own the user's goal;
- treat AI interpretation as authoritative user intent;
- silently convert a draft into execution authority;
- change user intent;
- create its own project canon;
- make strategic decisions on behalf of the user;
- treat its own claim of success as authoritative proof.

## LEVEL 1 — FOUNDATION

### F0. Request-to-Contract Boundary

Defines and enforces the transition:

```text
REQUEST
  -> INTERPRETATION
  -> DRAFT CONTRACT
  -> HUMAN AUTHORIZATION
  -> FROZEN CONTRACT
```

Formation is governed. No non-authorized formation state may enter the execution kernel.

### F1. Contract Interpretation Boundary

The execution kernel receives project/task contracts, constraints, acceptance criteria and authority. It does not override them.

Formation may propose contract fields before authorization, but the kernel executes only the frozen contract.

### F2. Source & Workspace Access

Includes:

- repository access;
- source acquisition;
- pinned input identity;
- workspace lifecycle;
- controlled inputs.

### F3. Execution State Model

Executor needs explicit formation and execution lifecycles, including bounded transitions, blocked/failed outcomes and replay/revalidation behavior.

Formation state and execution state must not be collapsed into one implicit model state.

### F4. Evidence Boundary

Executor records actions, artifacts and observable technical results. Execution evidence is not the same as human acceptance, product truth or strategic lineage.

## LEVEL 2 — CORE STRUCTURE

### S0. Contract Formation Flow

```text
User Request
      |
      v
Interpret
      |
      v
Propose Draft
      |
      v
Critique
      |
      v
Present Decision Surface
      |
      v
Human Authorization
      |
      v
Frozen Task Contract
```

Question answered:

> What explicit action boundary should be presented to the user for authorization?

Not:

> What should the user's goal really be?

### S1. Runtime Engine

```text
Frozen Task Contract
      |
      v
 Runtime Engine
      |
      +--> Plan
      +--> Execute
      +--> Observe
      +--> Verify
      +--> Report
```

### S2. Planning Layer

Question answered:

> How do we execute the approved contract?

Not:

> What should the user's goal really be?

### S3. Action Execution Layer

Bounded operations such as:

- file operations;
- Git operations;
- commands;
- tests;
- explicitly authorized tools.

### S4. Verification Loop

```text
ACTION
  |
RESULT
  |
VALIDATION
  |
ACCEPTABLE TECHNICAL RESULT / REJECTED / BLOCKED
```

The verification loop may establish technical facts. It does not grant product acceptance authority to Executor.

## LEVEL 3 — EXECUTION INFRASTRUCTURE

### I1. Execution State & Working Memory

Executor may own:

- current formation/run state;
- checkpoints;
- execution artifacts;
- action results;
- data needed for replay and recovery.

Executor does not own:

- the user's strategic goal;
- strategic decisions;
- project canon.

### I2. Context Management

Maintains the bounded working context needed to form or execute the current contract.

Formation context must distinguish user-supplied facts from AI inference.

### I3. Tool Management

Controls tool selection, capability exposure, constraints, credentials and execution conditions.

Contract-formation tools may gather context or propose fields; they do not themselves grant execution authority.

### I4. Sandbox & Isolation

Provides controlled execution, separation, blast-radius limits and fail-closed behavior.

## LEVEL 4 — CAPABILITY MODULES

Capabilities reuse Executor Core. They are not separate Executors by default.

```text
                 EXECUTOR CORE
                      |
          +-----------+-----------+
          |           |           |
       SOFTWARE    ANALYSIS    RESEARCH
          |           |           |
          +-----------+-----------+
                      |
                   ACTIONS
```

### C1. Software Engineering Capability

Repository analysis, code change and tests.

### C2. Analysis Capability

Structured data analysis, reports and bounded conclusions.

### C3. Research Capability

Information collection, comparison and synthesis within an authorized task or formation context.

Research may inform a draft. It may not silently expand the draft into executable authority.

### C4. Operational Capability

Repeatable procedures and bounded automation.

Capability does not imply authority.

## LEVEL 5 — USER EXPERIENCE

### UX1. Request Surface

Possible surfaces include chat, web UI, API or CLI.

The product front door is the user's request, not an internal contract file format.

A first user should be able to say:

```text
Fix the failing test about batch atomicity.
```

without knowing how the internal task contract is encoded.

### UX2. Contract Decision Surface

Before execution authority exists, expose only decision-relevant contract formation information:

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

### UX3. Execution Interaction Model

After authorization, the user should receive decision-relevant execution information, not internal command noise.

Preferred shape:

```text
AUTHORIZED TASK
PLAN
CHANGED
VERIFICATION
LIMITATIONS / DISCOVERIES
STATUS
```

### UX4. Result Report

Every completed attempt ends with a truthful result that distinguishes execution, verification, limitations and the next human decision.

## LEVEL 6 — EXTENSIONS

Possible later extensions include:

- capability marketplace;
- specialized role services;
- multi-agent deliberation;
- learning mechanisms;
- enterprise integrations.

These are not requirements for the first product slice.

## Cross-cutting rules

1. Human authority owns semantic goals and decisions.
2. AI interpretation is not authoritative user intent.
3. Request is not contract.
4. Draft contract is not authorized contract.
5. Contract formation is a governed action.
6. Contract bounds execution.
7. Deliberation may improve recommendations but may not expand authority.
8. Capability is not authority.
9. Validated authority must still match current authority-critical state at consequential action time.
10. Execution result is not accepted evidence.
11. Technical proof and product maturity remain separate from architectural existence.
12. A new component should remove a measured product or safety blocker, not merely add conceptual completeness.
