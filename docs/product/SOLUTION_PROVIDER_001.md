---
document: "SOLUTION_PROVIDER_001"
version: "0.1"
status: "STAGE 2 IMPLEMENTATION CANDIDATE"
date: "2026-08-27"
scope: "first bounded frozen-contract to validated-solution path"
repository: "FJ899/Executor"
---

# SOLUTION_PROVIDER_001

## Goal

Close only the second product transition:

```text
AUTHORIZED_AND_FROZEN
        |
        v
EXACT FROZEN SOURCE CONTEXT
        |
        v
EXTERNAL INTELLIGENCE
        |
        v
EXECUTOR-BOUND CANDIDATE
        |
        v
ValidatedSolutionProposal
```

The solution producer may propose code. It does not receive execution authority and it does not decide repository identity, source identity, writable scope, verification requirements or effect capability.

## Entry condition

`SolutionProvider` accepts only an existing frozen result that passes the shared immutable frozen-authority validator.

Before generation, Executor also recomputes the exact frozen contract hash. A caller-provided object that merely claims `AUTHORIZED_AND_FROZEN` is insufficient.

## Source-context rule

The source context is constructed by Executor, not supplied by the generator.

Executor verifies:

```text
repository == frozen target repository
HEAD commit == frozen target commit
HEAD tree == frozen target tree
allowed_paths == frozen task allowed_paths
allowed source bytes == bytes committed at the frozen commit
```

Only the frozen allowed files are exposed as writable solution context. A dirty or stale allowed file, wrong repository, wrong commit/tree or malformed scope blocks before the generator is called.

## Generator boundary

The generator receives a deterministic prompt containing:

- frozen contract hash;
- frozen target;
- frozen task;
- exact bounded source context;
- an explicit no-effect output contract.

The generator may return only:

```text
schema_version
mutations:
  - path
    replacement_text
rationale
```

It cannot supply or override:

- repository;
- source commit/tree;
- frozen contract hash;
- before/after hashes;
- evidence plan;
- proposal identity;
- authorization/effect metadata.

Attempted scope expansion or additional mutation metadata fails closed.

## Executor-owned bindings

For each accepted generator mutation Executor derives:

```text
expected_before_sha256 = SHA256(exact verified frozen-source bytes)
expected_after_sha256  = SHA256(generator replacement UTF-8 bytes)
```

Executor also derives:

- repository, commit and tree from the frozen context;
- verification plan from frozen `postcondition_argv` and `regression_argv`;
- deterministic proposal id from frozen/context/prompt/generation binding;
- provenance from the provider boundary.

The result is passed through the existing `materialize_solution_candidate()` and `validate_solution_proposal()` path. Stage 2 does not create a parallel proposal validator.

## Provenance

Stage 2 uses:

```text
executor-solution-provenance/1.1
```

Required provenance binds at least:

- producer role;
- provider;
- model;
- generated_at;
- exact request evidence identity;
- exact frozen contract SHA-256;
- exact source repository/commit/tree;
- exact source-context SHA-256;
- exact prompt SHA-256;
- `human_solution_edits = 0`;
- `effect_capability = NONE`;
- derivation after frozen contract.

`generated_at` must be later than both the original human request and the frozen-authority verification instant.

## Fail-closed conditions

Stage 2 blocks at least:

```text
invalid or fabricated frozen authority
frozen contract hash mismatch
wrong repository identity
wrong HEAD commit
wrong source tree
stale/dirty allowed source file
scope expansion
protected/out-of-scope mutation
missing or invalid provenance
pre-freeze solution provenance
source/request/frozen/context/prompt binding mismatch
invalid after hash
missing frozen verification commands
attempted effect-authority metadata
```

## Effect boundary

The solution generator receives no Executor ledger, runtime, sandbox mutation handle, GitHub write client or action-authorization handle.

Stage 2 result remains effect-free:

```text
effect_capability: NONE
status: VALIDATED_SOLUTION_PROPOSAL
```

A valid proposal is not execution authority.

## Non-goals

This stage does not implement:

- applying the proposed mutation;
- sandbox execution;
- branch creation;
- commit creation;
- push;
- draft PR creation;
- retry/recovery effects;
- merge;
- release;
- deploy;
- tag;
- a new task class;
- a new network/model client;
- Stage 3 capability.

## Acceptance criteria

Evidence is required for:

```text
valid frozen authority + exact source + bounded generator output
    -> ValidatedSolutionProposal

invalid/fabricated frozen authority
    -> BLOCK

wrong repo/commit/tree or dirty source
    -> BLOCK BEFORE GENERATOR

out-of-scope generator mutation
    -> BLOCK

generator tries to control Executor-owned hashes/metadata
    -> BLOCK

before/after hashes
    -> DERIVED BY EXECUTOR

verification plan
    -> DERIVED FROM FROZEN CONTRACT

provenance
    -> AUTO-BOUND TO REQUEST + FROZEN + SOURCE + CONTEXT + PROMPT

provider effect capability
    -> NONE
```

The terminal transition for this stage is exactly:

```text
AUTHORIZED_AND_FROZEN -> SolutionProvider -> ValidatedSolutionProposal
```
