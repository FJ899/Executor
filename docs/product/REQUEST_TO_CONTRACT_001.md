---
document: "REQUEST_TO_CONTRACT_001"
version: "0.2"
status: "FORMATION PHASE 1 ACCEPTED ON MAIN / VERIFIED HUMAN AUTHORITY PENDING"
date: "2026-08-09"
scope: "first governed request-to-contract formation slice for existing GP001"
repository: "JTJ07/Executor"
---

# REQUEST_TO_CONTRACT_001

## Goal

Prove the first safe portion of the product transition:

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
AWAITING VERIFIED HUMAN AUTHORIZATION
```

This phase intentionally stops there.

It does **not** create `AUTHORIZED_AND_FROZEN`, because the repository does not yet contain an independently verified human-authority evidence boundary for contract formation.

## Why phase 1 stops before freeze

The first implementation attempted to accept a process-local object labelled `HUMAN_AUTHORITY` and use it to freeze the draft.

Adversarial review rejected that design.

A caller-controlled string or object is not evidence that a human made a decision. Accepting it would repeat the earlier false-authority class in a new layer.

The required rule is:

```text
SELF-DECLARED HUMAN AUTHORITY
        !=
VERIFIED HUMAN AUTHORITY
```

Therefore the formation kernel is fail-closed until a superior boundary can provide independently verified evidence bound to the exact current draft.

## What phase 1 implements

Phase 1 was accepted through PR #50 and is available through the bounded `form-gp001-request` CLI command.

`executor/request_to_contract.py`:

- records the verbatim user request;
- treats that verbatim request as the only direct `USER` provenance available to this kernel;
- records structured interpretation as `MODEL` provenance;
- does not let a caller inject additional fields labelled `USER`;
- uses the canonical `REQUEST_TO_CONTRACT_001` profile rather than a caller-selected profile;
- records out-of-scope discoveries separately from executable scope;
- records unresolved questions;
- creates a hash-bound draft;
- critiques the proposed executable task against the accepted GP001 contract;
- blocks a divergent contract or unresolved question;
- exports a human-authorization request bound to the exact draft, canonical formation profile and canonical GP001 task hashes;
- never returns an executable or frozen task contract in phase 1.

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

All phase-1 surfaces contain:

```text
executable: false
```

A clean draft ends at:

```text
AWAITING_VERIFIED_HUMAN_AUTHORIZATION
```

## Provenance rule

The only direct user evidence currently accepted by this kernel is the verbatim request:

```text
source: USER
path: $.user_request
```

Repository, test, scope and other structured interpretation records are model/process proposals:

```text
source: MODEL
```

This prevents a caller from laundering model inference into apparent user intent by merely labelling it `USER`.

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

## Human authorization request

For a clean critiqued draft, phase 1 emits a non-executable request containing:

```text
draft_sha256
formation_profile_sha256
canonical_task_sha256
allowed_decisions: ACCEPT / MODIFY / REJECT
required_authority: VERIFIED_EXTERNAL_HUMAN_AUTHORITY
status: AWAITING_VERIFIED_HUMAN_AUTHORIZATION
```

These bindings are material for a later trusted authority boundary. They are not themselves proof of human authorization.

## Adversarial finding retained

```text
F-4 — SELF-DECLARED FORMATION AUTHORITY

initial design:
caller-created HumanDecisionReceipt("HUMAN_AUTHORITY")
        -> AUTHORIZED_AND_FROZEN

verdict:
REJECTED

phase-1 correction:
no caller decision API
no freeze API
no executable contract
clean draft stops at AWAITING_VERIFIED_HUMAN_AUTHORIZATION
```

## Non-goals

This phase does not implement:

- a language model;
- prompt templates;
- general natural-language understanding;
- arbitrary task generation;
- automatic authorization;
- verified human identity / decision evidence;
- `AUTHORIZED_AND_FROZEN` transition;
- execution of the draft;
- GP002;
- separate proposer/critic agents;
- multi-agent orchestration.

## Acceptance question

This PR answers only:

> Can Executor preserve user/model provenance, construct and critique one known GP001 draft, prevent silent scope expansion, and stop safely at the verified-human-authority boundary?

It does not yet answer:

> Can an authenticated human decision freeze that draft for execution?

That becomes the next explicit blocker rather than an implied capability.
