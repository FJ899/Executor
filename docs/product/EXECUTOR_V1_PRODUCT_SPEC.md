---
document: "Executor v1 Product Spec"
version: "1.0"
status: "USER APPROVED CONCEPT / PENDING REPO MERGE"
date: "2026-08-08"
scope: "first user, first product promise, first end-to-end workflow and explicit non-goals"
repository: "litrgratis-pixel/Executor"
---

# Executor v1 Product Spec

## 1. Purpose of this document

This document answers one product question:

> What can the first user actually do with Executor?

`v1` in this document means the **first product slice specification**. It is not a claim that the repository has reached release `1.0`, and it does not replace the P0-Pn maturity ladder. Product scope and maturity proof are separate axes.

## 2. First user

The first user is a software developer or engineer working with a code repository.

The first product is not aimed at every user, every company workflow, or every digital task.

## 3. One product promise

> Executor safely performs a well-defined technical task in a repository and shows what changed and whether the change works.

Executor is not the owner of the user's goal. It receives a bounded task contract and executes within it.

## 4. Golden Path #001

The first complete user scenario is:

> **Fix a failing test.**

Example input:

```text
Fix the failing test in this repository.
```

Expected user-visible flow:

```text
USER TASK
   |
   v
TASK CONTRACT
   |
   v
REPRODUCE FAILURE
   |
   v
ANALYZE
   |
   v
PROPOSE BOUNDED PLAN
   |
   v
HUMAN AUTHORIZATION
   |
   v
EXECUTE
   |
   v
VERIFY
   |
   v
REPORT
```

## 5. Product workflow

### Step 1 — Receive a bounded task

Required input must identify at least:

- repository and pinned input state;
- problem to solve;
- expected result;
- acceptance criteria;
- allowed change scope;
- required verification;
- prohibited actions.

Missing required authority or acceptance information results in `BLOCKED`, not guessing.

### Step 2 — Analyze the repository

Executor may:

- inspect repository structure;
- read relevant files;
- reproduce the failing test;
- identify likely dependencies;
- discover related issues.

Discovery does not expand execution authority.

Out-of-contract findings are reported as recommendations for a separate task.

### Step 3 — Produce a bounded plan

The plan answers:

> How can the approved task contract be executed?

It does not redefine what the user should want.

For the golden path, the plan should be short and reviewable, for example:

```text
1. Modify src/validator.py.
2. Do not modify the failing test.
3. Run the target test.
4. Run the regression suite.
5. Report the diff and verification result.
```

### Step 4 — Human authorization

Before the first product slice performs repository mutation, the user must be able to accept, modify, or cancel the proposed execution plan when the plan is not already fully authorized by the task contract.

Recommendation is not authorization.

### Step 5 — Execute

Minimum v1 actions:

- read file;
- edit file;
- create file when explicitly permitted;
- run an allowed command;
- inspect Git diff;
- run required tests.

Execution remains bounded by contract, policy, workspace, and sandbox constraints.

### Step 6 — Verify

A successful golden-path candidate requires all of the following:

```text
TARGET FAILURE REPRODUCED BEFORE CHANGE: YES
TARGET TEST AFTER CHANGE: PASS
REQUIRED REGRESSION CHECKS: PASS
CHANGE SCOPE: WITHIN CONTRACT
PROHIBITED TEST WEAKENING: NOT DETECTED
```

A target test turning green is not sufficient if the test was deleted, skipped, weakened, or otherwise bypassed outside explicit contract authority.

### Step 7 — Report

The user-facing report should prioritize the decision-relevant result rather than command count.

Minimum report:

```text
TASK:
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

## 6. What must exist for the first product slice

- a usable interface for starting the task;
- pinned repository/source access;
- task-contract validation;
- repository inspection;
- bounded planning;
- human authorization boundary;
- file/action execution;
- test execution;
- diff and scope verification;
- truthful final report;
- evidence sufficient to review the result.

## 7. What is intentionally not part of v1

The first product slice does not require:

- multi-agent orchestration;
- long-term project memory owned by Executor;
- autonomous strategic decisions;
- autonomous deployment;
- agent marketplace;
- generalized research product;
- enterprise integrations;
- support for arbitrary task classes;
- automatic merge.

Safety, evidence, isolation and governance may exist underneath the product slice, but they must not dominate the user-facing workflow.

## 8. Product success criteria

The first product slice is useful only if a real user can complete Golden Path #001 end to end and reviewing the produced change is cheaper than manually solving the same bounded problem.

Minimum product questions:

1. Could the user start the task without understanding internal Executor machinery?
2. Did Executor reproduce the failure before editing?
3. Did it stay inside the authorized scope?
4. Did it produce a sensible fix without the human writing the solution?
5. Did verification test the real acceptance condition rather than a proxy?
6. Is the final report short enough to support a human decision?
7. Is review cheaper than manual implementation?

## 9. Relationship to maturity

This product spec defines **what we are trying to make usable first**.

`EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` remains responsible for claims about P0, P1, P2, P3 and later maturity levels.

A feature may exist without its maturity proof. A maturity level may certify only a bounded slice. Architecture, implementation status, and proof status must not be collapsed into one claim.
