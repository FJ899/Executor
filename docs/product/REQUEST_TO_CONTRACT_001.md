---
document: "REQUEST_TO_CONTRACT_001"
version: "0.1"
status: "IMPLEMENTATION CANDIDATE / PENDING HUMAN REVIEW"
date: "2026-08-09"
scope: "first governed request-to-contract formation slice for existing GP001"
repository: "litrgratis-pixel/Executor"
---

# REQUEST_TO_CONTRACT_001

## Goal

Prove one narrow product transition:

```text
USER REQUEST
      |
      v
MODEL / PROCESS PROPOSAL
      |
      v
DRAFT TASK CONTRACT
      |
      v
CONTRACT CRITIQUE
      |
      v
HUMAN DECISION
      |
      v
AUTHORIZED_AND_FROZEN
```

The slice reuses the already accepted GP001 task and does not add a new execution capability.

## What the implementation does

`executor/request_to_contract.py`:

- records the verbatim user request;
- stores user facts separately from model inferences;
- records out-of-scope discoveries separately from executable scope;
- records unresolved questions;
- creates a hash-bound draft;
- critiques the proposed executable task against the accepted GP001 task profile;
- blocks authorization when the draft diverges or questions remain unresolved;
- supports human `ACCEPT`, `MODIFY` and `REJECT` transitions;
- invalidates prior review when `MODIFY` produces a new draft;
- freezes only an exact, valid GP001-compatible task contract after `ACCEPT` bound to the current draft hash.

## Decision surface

The formation kernel exposes:

```text
REQUEST
UNDERSTOOD OBJECTIVE
TARGET / INPUT IDENTITY
TARGET TEST
PROPOSED WRITE SCOPE
PROTECTED MATERIAL
SUCCESS CONDITIONS
DISCOVERED BUT OUT OF SCOPE
UNRESOLVED ASSUMPTIONS
PROVENANCE
CRITIQUE
DRAFT SHA-256
STATUS
```

Before authorization:

```text
executable: false
```

After the governed acceptance transition:

```text
status: AUTHORIZED_AND_FROZEN
```

## Provenance rule

The implementation keeps distinct records for:

```text
source: USER
source: MODEL
```

A model inference may appear in the draft and may be reviewed by the user. It is not rewritten as a user fact.

## Out-of-scope discovery rule

If the proposal discovers a broader issue, it remains metadata outside the current executable task.

Example:

```text
CURRENT TASK:
fix GP001 failing test

DISCOVERY:
registry architecture could be refactored more broadly

ACTION ON DISCOVERY:
none

AUTHORITY:
new contract required
```

## MODIFY semantics

`MODIFY` does not edit an already authorized contract.

It creates a new draft snapshot and a new `draft_sha256`, resets critique state, and requires a fresh critique plus a new decision.

Therefore:

```text
REVIEW OF DRAFT A
      !=
AUTHORITY FOR DRAFT B
```

## Explicit trust-boundary limitation

This slice does **not** authenticate a human identity.

The formation kernel accepts a `HumanDecisionReceipt` from a superior human-authority boundary and validates:

- decision kind;
- authority source classification;
- evidence reference presence;
- exact current draft SHA-256 binding.

It does not independently prove that the external evidence reference was genuinely created by a human. That identity/authentication boundary must remain outside this kernel and must not be claimed as solved by this PR.

## Non-goals

This slice does not implement:

- a language model;
- prompt templates;
- general natural-language understanding;
- arbitrary task generation;
- automatic authorization;
- human identity authentication;
- execution of the frozen contract;
- GP002;
- separate proposer/critic agents;
- multi-agent orchestration.

## Acceptance question

This PR answers only:

> Can Executor preserve the distinction between user request, model interpretation, draft authority and authorized frozen contract for the known GP001 task?

It does not claim that Executor can yet infer the correct GP001 contract from arbitrary natural language without an external interpretation proposal.
