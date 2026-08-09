---
document: "Golden Path 001 — Fix Failing Test"
version: "1.0"
status: "ACCEPTED PRODUCT PATH / MACHINE CONTRACT IN PHASE C"
date: "2026-08-09"
scope: "first end-to-end Executor user scenario"
repository: "litrgratis-pixel/Executor"
---

# Golden Path 001 — Fix Failing Test

## 1. User story

As a developer, I want to give Executor a repository with a reproducible failing test and receive a bounded code fix, verification evidence, and a concise report without having to implement the fix myself.

## 2. Why this is the first golden path

A failing test provides an observable before/after condition:

```text
BEFORE: target test FAILS
AFTER:  target test PASSES
```

That makes it a better first product scenario than an open-ended feature request.

However, green alone is not success. Executor must not obtain green by deleting, skipping, weakening, or bypassing the acceptance test unless the contract explicitly authorizes changing the test itself.

## 3. Input contract

The run requires:

- repository identity;
- exact input commit or equivalent pinned source identity;
- target failing test or deterministic reproduction command;
- expected behavior;
- allowed code paths;
- protected paths;
- required regression command(s);
- execution limits;
- explicit authorization boundary.

If the failure cannot be reproduced from the pinned baseline, the run is `BLOCKED` rather than silently redefining the problem.

## 4. Required flow

### GP001-01 — Acquire pinned input

The source used for analysis and execution must be tied to the declared input identity.

### GP001-02 — Reproduce failure before editing

Evidence must show the target failure exists before modification.

### GP001-03 — Analyze

Executor identifies the likely cause and relevant files.

Out-of-contract discoveries may be reported but do not change the authorized scope.

### GP001-04 — Plan

Executor produces a bounded plan specifying:

- intended files to modify;
- intended verification;
- important assumptions;
- any discovered out-of-contract issues.

### GP001-05 — Authorize

The plan must either already fall fully under the task contract or receive required human authorization before mutation.

### GP001-06 — Execute

Executor applies the smallest reasonable change inside the authorized scope.

### GP001-07 — Verify target

The target test must pass after the change.

### GP001-08 — Verify regressions

All contract-required regression checks must pass.

### GP001-09 — Verify scope

The resulting diff must remain within authorized paths and must not contain prohibited test weakening.

### GP001-10 — Report

Executor returns a concise review package and one of:

```text
ACTION_COMPLETED_REVIEW_REQUIRED
BLOCKED
FAILED
```

## 5. Minimum authoritative observations

A successful candidate requires evidence for:

```text
INPUT IDENTITY: MATCH
PRE-CHANGE TARGET TEST: FAIL
POST-CHANGE TARGET TEST: PASS
REGRESSION CHECKS: PASS
DIFF SCOPE: ALLOWED
PROTECTED TEST / ACCEPTANCE MATERIAL: UNCHANGED OR EXPLICITLY AUTHORIZED
EXECUTION LIMITS: RESPECTED
RESULT ARTIFACT: PRESENT
```

## 6. Anti-cheating cases

The path must fail closed when a candidate attempts to obtain green by:

- deleting the failing test;
- skipping or xfail-marking the test without contract authority;
- changing the assertion to accept broken behavior;
- changing test discovery so the test does not run;
- modifying unrelated code outside allowed scope;
- changing the baseline identity;
- running a different command and reporting it as the required test;
- claiming success without required regression evidence.

## 7. Product report

Minimum user-facing report:

```text
TASK:
Fix failing test <id>.

CAUSE:
Short explanation.

CHANGED:
- path(s)

VERIFICATION:
- pre-change reproduction: FAIL confirmed
- target test: PASS
- regression checks: PASS
- scope check: PASS

DISCOVERIES / LIMITATIONS:
...

STATUS:
ACTION_COMPLETED_REVIEW_REQUIRED
```

## 8. Definition of completion for GP001

Golden Path #001 is not complete because supporting components exist individually.

It is complete only when the full path is demonstrated end to end on a pinned repository input, with a real failing condition, no manual solution edit by the user, truthful evidence, and a reviewable result.

Fixture runs may develop the path. Product proof requires a real repository task consistent with the applicable maturity gate.

## 9. Machine-readable Phase C contract

The first bounded development instance of GP001 is pinned to the controlled `CASE-001` regression in `litrgratis-pixel/executor-pilot-target`.

Machine-readable sources:

```text
tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml
test_contracts/GP001_FIX_FAILING_TEST_CASE_001.yaml
tests/fixtures/gp001/contract_source.json
```

The GP001-specific structural validator is:

```text
python -m executor.gp001_contract tasks/GP001_FIX_FAILING_TEST_CASE_001.yaml
```

The contract fixes, before execution:

- target repository and exact commit;
- exact failing test;
- one exact allowed code path;
- protected acceptance/test paths;
- report-only treatment of out-of-scope discoveries;
- explicit authorization requirement before mutation;
- exact target and regression commands;
- bounded model/execution/time/patch budgets;
- required before/after/scope observations;
- terminal result limited to `ACTION_COMPLETED_REVIEW_REQUIRED`, `BLOCKED`, or `FAILED`.

The controlled CASE-001 input is a development vehicle for the vertical path. Passing it will not by itself claim product value, a new maturity level, or completion of GP001 on a real repository task.

Until repository identity and run evidence are independently available, authoritative validation is expected to remain evidence-blocked rather than infer execution readiness.
