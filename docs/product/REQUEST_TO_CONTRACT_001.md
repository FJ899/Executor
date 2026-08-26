---
document: "REQUEST_TO_CONTRACT_001"
version: "0.3"
status: "FORMATION -> VERIFIED GITHUB DECISION -> FREEZE IMPLEMENTED"
date: "2026-08-26"
scope: "first governed request-to-contract formation path for existing GP001"
repository: "FJ899/Executor"
---

# REQUEST_TO_CONTRACT_001

## Goal

Implement the first complete governed formation path for the existing GP001 task:

```text
USER REQUEST
      |
      v
MODEL / PROCESS PROPOSAL
      |
      v
GOVERNED DRAFT
      |
      v
CONTRACT CRITIQUE
      |
      v
AWAITING VERIFIED HUMAN AUTHORIZATION
      |
      v
VERIFIED GITHUB DECISION
      |
      +---- ACCEPT ----> AUTHORIZED_AND_FROZEN
      |
      +---- MODIFY ----> OLD DRAFT INVALIDATED -> NEW DRAFT -> NEW DECISION REQUIRED
      |
      +---- REJECT ----> FORMATION TERMINATED / NO EXECUTION AUTHORITY
```

The implementation reuses the existing provider-verified GitHub authority and P4 freeze boundary. It does not introduce a second authority mechanism.

## Authority rule

The retained invariant is:

```text
SELF-DECLARED HUMAN AUTHORITY
        !=
VERIFIED HUMAN AUTHORITY
```

`RequestToContract001` still does not accept a caller-created object labelled as human authority. Executable authority can only arise after GitHub provider evidence has been verified for the exact current request and exact current formation draft hash.

Edited, expired, stale, mismatched, app-mediated, wrong-actor or otherwise unverifiable decisions remain blocked by the GitHub trust boundary.

## Formation behavior

`executor/request_to_contract.py`:

- preserves the verbatim user request as the only direct `USER` provenance;
- records structured interpretation as `MODEL` provenance;
- uses the canonical `REQUEST_TO_CONTRACT_001` profile and accepted GP001 task source;
- keeps out-of-scope discoveries report-only;
- blocks unresolved questions and contract divergence;
- creates a hash-bound, versioned formation draft;
- generates the bounded GitHub authority request payload from the current governed draft rather than requiring a separately hand-authored request JSON;
- derives the exact target tree from provider commit evidence;
- verifies the provider request equals the generated formation request before accepting any decision;
- binds the verified GitHub decision to the exact current formation `draft_sha256`;
- delegates final-live verification, immutable authority snapshot construction and authority consumption to the existing P4 freeze boundary;
- stores formation provenance and the generated authority-request payload in the frozen contract as `formation_binding`.

The shared P4 freeze independently validates formation-mode before authority consumption. Mutual consistency between caller-supplied hashes and objects is not enough. It validates the full formation-draft schema, USER/MODEL provenance, absence of unresolved questions and structural GP001 validity, then derives the expected GitHub request projection from the hashed `proposed_task_contract`.

That independent projection must match the provider-verified request for:

```text
request_id
target repository
target commit
task class
problem statement
allowed paths
protected paths
precondition command
postcondition command
regression commands
max production files
max patch lines
deterministic formation nonce
```

Target tree identity is still verified independently from provider commit evidence, while request/decision freshness remains enforced by the existing GitHub trust boundary.

Therefore a self-consistent forged formation draft/hash/binding with a request payload that was not derived from that draft is blocked before authority consumption.

## ACCEPT

A verified `ACCEPT` may produce:

```text
status: AUTHORIZED_AND_FROZEN
executable: true
```

The frozen contract binds at least:

```text
request_id
formation draft version
formation draft sha256
formation profile sha256
canonical GP001 task sha256
target repository
target commit
target tree
allowed/protected scope
verified request evidence
verified decision evidence
authority snapshot
authority consumption receipt
```

The frozen contract remains compatible with the existing P4 frozen-authority validator.

## MODIFY

A verified `MODIFY` never freezes the current draft.

It transitions formation to:

```text
MODIFICATION_REQUIRED
```

The current draft hash is recorded as invalidated. A revision:

- increments `draft_version`;
- records `supersedes_draft_sha256`;
- produces a new draft hash even when the bounded task content remains otherwise identical;
- requires a new generated authority request and a new verified human decision.

An `ACCEPT` referring to the superseded draft cannot authorize the new draft.

## REJECT

A verified `REJECT` transitions formation to:

```text
REJECTED
```

No frozen contract or execution authority is created.

## GitHub authority request generation

For the current GP001 formation profile, Executor derives the provider request from the governed draft:

```text
formation draft
    -> canonical GP001 target/scope/commands/budget
    -> provider-verified target commit/tree
    -> executor-github-request/1.0 payload
```

The dedicated trust profile is:

```text
trust_profiles/github-request-to-contract-001.json
```

The target remains deliberately bounded to:

```text
FJ899/executor-pilot-target
```

This is not a general task or repository authorization capability.

## Provenance rule

The only direct user evidence accepted inside formation remains the verbatim request:

```text
source: USER
path: $.user_request
```

Repository, test, scope and other structured interpretation values are model/process proposals until the exact governed draft is externally accepted by verified human authority.

## Non-goals

This stage does not implement:

- general natural-language understanding;
- arbitrary task-contract generation;
- solution generation;
- solution-provider routing;
- execution;
- branch/push/PR effects;
- additional task classes;
- multi-user or multi-agent authority;
- merge, deploy, release or tag authority.

## Acceptance criteria

Stage 1 requires evidence for:

```text
ACCEPT current draft -> AUTHORIZED_AND_FROZEN
ACCEPT superseded draft after MODIFY -> BLOCK
REJECT -> no frozen contract
MODIFY -> previous draft invalidated and new decision required
edited decision -> BLOCK
expired decision -> BLOCK
mismatched decision/request -> BLOCK
no verified authority -> no freeze
custom formation authority hash without complete binding -> BLOCK
tampered formation draft content after hashing -> BLOCK
self-consistent binding with request payload not derived from governed draft -> BLOCK
```

The intended terminal product transition for this stage is:

```text
normal user request
    -> governed draft
    -> generated bounded authority request
    -> verified human decision
    -> AUTHORIZED_AND_FROZEN
```

No solution generation or execution authority is added by this stage.
