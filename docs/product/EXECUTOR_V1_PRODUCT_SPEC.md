---
document: "Executor v1 Product Spec"
version: "1.1"
status: "USER ACCEPTED DIRECTION / PHASE B P4 IMPLEMENTATION CANDIDATE"
date: "2026-08-09"
scope: "first user, request-to-contract front door, first product promise, first end-to-end workflow and explicit non-goals"
repository: "JTJ07/Executor"
---

# Executor v1 Product Spec

## 1. Purpose of this document

This document answers one product question:

> What can the first user actually do with Executor System?

`v1` in this document means the **first product-slice specification**. It is not a claim that the repository has reached release `1.0`, and it does not replace the P0-Pn maturity ladder. Product scope and maturity proof are separate axes.

Executor is a system. The execution program/kernel is one part of that system.

## 2. First user

The first user is a software developer or engineer working with a code repository.

The first product is not aimed at every user, every company workflow, or every digital task.

## 3. One product promise

> Executor System turns a bounded user request into an explicit contract proposal, requires authorization before that proposal becomes executable, then performs the authorized repository task and shows what changed and whether the change works.

Executor is not the owner of the user's goal.

The formation layer may interpret and propose. The human owns authorization of the contract. The execution kernel executes the frozen contract.

## 4. Three product layers

### Level 1 — User Experience

What the human sees:

```text
Fix the failing test about batch atomicity.
```

The user should not need to understand task YAML, AAP packets, Python classes, Docker workflows or internal model prompts.

### Level 2 — Cognitive / Contract Layer

Responsible for:

```text
INTERPRET
   -> PROPOSE DRAFT CONTRACT
   -> CRITIQUE
   -> PRESENT FOR HUMAN DECISION
```

Prompts and AI roles may exist here, but they do not create execution authority by themselves.

### Level 3 — Execution Kernel

Responsible for:

- contract validation;
- policy enforcement;
- action authorization;
- sandbox execution;
- file/Git/test/tool operations;
- execution state;
- evidence collection;
- verification and truthful reporting.

The kernel executes an authorized contract. It does not infer what the user "really meant".

## 5. Golden Path #001

The first complete technical scenario remains:

> **Fix a failing test.**

The accepted GP001 runtime has already demonstrated the bounded execution half of the product path.

The front-half candidate now exists through exact GitHub request/decision evidence. The remaining product gap is real external proof:

```text
USER REQUEST
   |
   v
DRAFT TASK CONTRACT
   |
   v
CONTRACT CRITIQUE
   |
   v
HUMAN AUTHORIZATION
   |
   v
FROZEN TASK CONTRACT
   |
   v
EXISTING GP001 RUNTIME
   |
   v
ACTION_COMPLETED_REVIEW_REQUIRED
```

## 6. Product workflow

### Step 0 — Receive the user request

The first user-facing input may be natural language, for example:

```text
Fix the failing test about batch atomicity.
```

The request is not automatically executable authority.

### Step 1 — Form a draft task contract

The system proposes explicit fields including:

- understood objective;
- repository and pinned input state;
- target test or acceptance condition;
- proposed write scope;
- protected material;
- expected result;
- required verification;
- prohibited actions;
- out-of-scope discoveries;
- unresolved assumptions.

The draft must remain visibly non-executable.

Core rules:

```text
REQUEST != CONTRACT
AI INTERPRETATION != USER INTENT
DRAFT CONTRACT != AUTHORIZED CONTRACT
```

### Step 2 — Critique the draft

Critique asks whether the proposed contract:

- silently expanded the request;
- inferred unsupported authority;
- omitted a material ambiguity;
- weakened acceptance criteria;
- included discovered work that belongs in a separate contract.

Critique improves the proposal. It does not authorize it.

### Step 3 — Human authorization

The user must be able to:

```text
ACCEPT
MODIFY
REJECT
```

Only an accepted contract becomes frozen execution authority.

### Step 4 — Analyze the repository

After authorization, Executor may:

- inspect repository structure;
- read relevant files;
- reproduce the failing test;
- identify likely dependencies;
- discover related issues.

Discovery does not expand execution authority.

Out-of-contract findings are reported as recommendations for a separate task.

### Step 5 — Produce a bounded execution plan

The plan answers:

> How can the approved task contract be executed?

It does not redefine what the user should want.

### Step 6 — Execute

Minimum v1 actions:

- read file;
- edit file;
- create file when explicitly permitted;
- run an allowed command;
- inspect Git diff;
- run required tests.

Execution remains bounded by contract, policy, workspace and sandbox constraints.

### Step 7 — Verify

A successful golden-path candidate requires all of the following:

```text
TARGET FAILURE REPRODUCED BEFORE CHANGE: YES
TARGET TEST AFTER CHANGE: PASS
REQUIRED REGRESSION CHECKS: PASS
CHANGE SCOPE: WITHIN CONTRACT
PROHIBITED TEST WEAKENING: NOT DETECTED
```

A target test turning green is not sufficient if the test was deleted, skipped, weakened or otherwise bypassed outside explicit contract authority.

### Step 8 — Report

The user-facing report should prioritize the decision-relevant result rather than command count.

Minimum report:

```text
REQUEST:
...

AUTHORIZED CONTRACT:
...

PLAN:
...

CHANGED:
...

VERIFICATION:
...

LIMITATIONS / DISCOVERIES:
...

STATUS:
ACTION_COMPLETED_REVIEW_REQUIRED | BLOCKED | FAILED
```

## 7. What must exist for the first product slice

- a natural-language or equally simple request surface;
- governed request-to-contract formation;
- visible draft-contract state;
- contract critique for unsupported inference/scope expansion;
- human contract-authorization boundary;
- pinned repository/source access;
- task-contract validation;
- repository inspection;
- bounded planning;
- action authorization;
- file/action execution;
- test execution;
- diff and scope verification;
- truthful final report;
- evidence sufficient to review the result.

## 8. What is intentionally not part of v1

The first product slice does not require:

- general natural-language understanding for arbitrary domains;
- multi-agent orchestration;
- separate proposer/critic/researcher services;
- long-term project memory owned by Executor;
- autonomous strategic decisions;
- autonomous contract authorization;
- autonomous deployment;
- agent marketplace;
- generalized research product;
- enterprise integrations;
- support for arbitrary task classes;
- automatic merge.

Safety, evidence, isolation and governance may exist underneath the product slice, but they must not dominate the user-facing workflow.

## 9. Product success criteria

The first product slice is useful only if a real user can start with a normal request and complete Golden Path #001 end to end without manually constructing internal Executor machinery.

Minimum product questions:

1. Could the user start with a normal request rather than a hand-authored internal contract?
2. Did the system distinguish interpretation from user-authorized intent?
3. Did the draft expose its proposed scope and assumptions before execution authority existed?
4. Did critique detect or report attempted scope expansion?
5. Could the user accept, modify or reject the draft?
6. Did Executor reproduce the failure before editing?
7. Did it stay inside the authorized scope?
8. Did it produce a sensible fix without the human writing the solution?
9. Did verification test the real acceptance condition rather than a proxy?
10. Is the final report short enough to support a human decision?
11. Is review cheaper than manual implementation?

## 10. Relationship to maturity

This product spec defines **what we are trying to make usable first**.

`EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` remains responsible for claims about P0, P1, P2, P3 and later maturity levels.

A feature may exist without its maturity proof. A maturity level may certify only a bounded slice. Architecture, implementation status and proof status must not be collapsed into one claim.
