---
document: "Executor Build Map"
version: "1.0"
status: "USER APPROVED CONCEPT / PENDING REPO MERGE"
date: "2026-08-08"
scope: "canonical architectural decomposition of Executor"
repository: "litrgratis-pixel/Executor"
---

# Executor Build Map v1

## 1. Purpose

This map answers:

> What are we actually building?

It is an architecture map, not a maturity certificate and not an implementation inventory.

Three separate questions remain separate:

- **Build Map** — what belongs to the system;
- **Implementation Inventory** — what currently exists;
- **Maturity / Proof Ladder** — what has been proven.

`HUMAN_AI_DELIBERATION_MODEL.md` is a cross-cutting way of working and is not a fourth build axis.

## LEVEL 0 — PRODUCT DEFINITION

Executor does not own the goal.

```text
HUMAN / SUPERIOR SYSTEM
          |
          v
   PROJECT CONTRACT
          |
          v
    TASK CONTRACT
          |
          v
       EXECUTOR
          |
          +--> interprets the contract
          +--> plans execution
          +--> executes
          +--> verifies technical result
          +--> reports
```

Core definition:

> Executor turns an approved action contract into a safely executed, observable and independently reviewable digital change.

Executor does not:

- define the user's goal;
- change user intent;
- create its own project canon;
- make strategic decisions on behalf of the user;
- treat its own claim of success as authoritative proof.

## LEVEL 1 — FOUNDATION

### F1. Contract Interpretation Boundary

Executor receives project/task contracts, constraints, acceptance criteria and authority. It does not override them.

### F2. Source & Workspace Access

Includes:

- repository access;
- source acquisition;
- pinned input identity;
- workspace lifecycle;
- controlled inputs.

### F3. Execution State Model

Executor needs an explicit execution lifecycle, including bounded transitions, blocked/failed outcomes and replay/revalidation behavior.

### F4. Evidence Boundary

Executor records actions, artifacts and observable technical results. Execution evidence is not the same as human acceptance, product truth, or strategic lineage.

## LEVEL 2 — CORE STRUCTURE

### S1. Runtime Engine

```text
Task Contract
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

- current run state;
- checkpoints;
- execution artifacts;
- action results;
- data needed for replay and recovery.

Executor does not own:

- the user's strategic goal;
- strategic decisions;
- project canon.

### I2. Context Management

Maintains the bounded working context needed to execute the current contract.

### I3. Tool Management

Controls tool selection, capability exposure, constraints, credentials and execution conditions.

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

Information collection, comparison and synthesis within an authorized task.

### C4. Operational Capability

Repeatable procedures and bounded automation.

Capability does not imply authority.

## LEVEL 5 — USER EXPERIENCE

### UX1. Interface

Possible surfaces include CLI, API, chat and web UI.

### UX2. Interaction Model

The user should receive the result and decision-relevant evidence, not internal command noise.

Preferred shape:

```text
TASK
PLAN
CHANGED
VERIFICATION
LIMITATIONS / DISCOVERIES
STATUS
```

### UX3. Result Report

Every completed attempt ends with a truthful result that distinguishes execution, verification, limitations and the next human decision.

## LEVEL 6 — EXTENSIONS

Possible later extensions include:

- capability marketplace;
- specialized roles;
- multi-agent deliberation;
- learning mechanisms;
- enterprise integrations.

These are not requirements for the first product slice.

## Cross-cutting rules

1. Human authority owns semantic goals and decisions.
2. Contract bounds execution.
3. Deliberation may improve recommendations but may not expand authority.
4. Capability is not authority.
5. Execution result is not accepted evidence.
6. Technical proof and product maturity remain separate from architectural existence.
7. A new component should remove a measured product or safety blocker, not merely add conceptual completeness.
