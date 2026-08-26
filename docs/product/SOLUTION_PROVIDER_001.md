---
document: "SOLUTION_PROVIDER_001"
version: "0.2"
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
INDEPENDENT GENERATION EVIDENCE
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

The generator adapter may return only:

```text
schema_version: executor-solution-generation/1.1
evidence_ref
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

`evidence_ref` is not treated as proof by itself. It is only a lookup key for the separate generation-evidence verifier.

## Independent generation-evidence boundary

Stage 2 does **not** assign a fresh timestamp or current frozen/context/prompt bindings to arbitrary generator content after the response arrives.

After the generator returns, Executor computes the canonical SHA-256 of the exact generation response payload:

```text
response_sha256 = SHA256(schema_version + mutations + rationale)
```

A separate read-only `SolutionGenerationVerifier` resolves the returned `evidence_ref` independently of the generator response and returns `VerifiedGenerationEvidence`.

That verified provider record must bind exactly:

```text
evidence_ref
provider
model
generated_at
frozen_contract_sha256
repository
commit
tree
context_sha256
prompt_sha256
response_sha256
verification_method
```

Executor compares every binding against the current frozen input and the response it actually received.

Therefore:

- a cached response from frozen contract A replayed against frozen contract B retains evidence for A and is blocked;
- an old provider response whose provider timestamp does not postdate the current freeze is blocked;
- content changed while reusing an old `evidence_ref` changes `response_sha256` and is blocked;
- an evidence record for another source/context/prompt is blocked;
- Executor cannot make stale content look fresh merely by calling its own clock after generation.

The generation verifier is a trusted **verification** boundary only. It receives no Executor effect-authority handle and creates no external effect.

## Executor-owned bindings

For each accepted generator mutation Executor derives:

```text
expected_before_sha256 = SHA256(exact verified frozen-source bytes)
expected_after_sha256  = SHA256(generator replacement UTF-8 bytes)
```

Executor also derives:

- repository, commit and tree from the frozen context;
- verification plan from frozen `postcondition_argv` and `regression_argv`;
- deterministic proposal id from frozen/context/prompt/verified-generation binding;
- proposal provenance from the independently verified generation record.

The result is passed through the existing `materialize_solution_candidate()` and `validate_solution_proposal()` path. Stage 2 does not create a parallel proposal validator.

## Provenance

Stage 2 uses:

```text
executor-solution-provenance/1.2
```

Required provenance binds at least:

- producer role;
- provider;
- model;
- provider-evidenced `generated_at`;
- exact request evidence identity;
- exact frozen contract SHA-256;
- exact source repository/commit/tree;
- exact source-context SHA-256;
- exact prompt SHA-256;
- generation evidence reference;
- exact generation response SHA-256;
- generation verification method;
- `human_solution_edits = 0`;
- `effect_capability = NONE`;
- derivation after frozen contract.

`generated_at` comes from independently verified generation evidence and must be later than both the original human request and the frozen-authority verification instant.

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
missing generation evidence
pre-freeze verified generation
cross-contract generation evidence replay
cross-source/context/prompt generation evidence replay
response content changed under old evidence_ref
source/request/frozen/context/prompt binding mismatch
invalid after hash
missing frozen verification commands
attempted effect-authority metadata
```

## Effect boundary

The solution generator and generation verifier receive no Executor ledger, runtime, sandbox mutation handle, GitHub write client or action-authorization handle.

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
+ independently verified exact generation evidence
    -> ValidatedSolutionProposal

invalid/fabricated frozen authority
    -> BLOCK

wrong repo/commit/tree or dirty source
    -> BLOCK BEFORE GENERATOR

out-of-scope generator mutation
    -> BLOCK

generator tries to control Executor-owned hashes/metadata
    -> BLOCK

cached response A + evidence A used against frozen/source/context B
    -> BLOCK

changed response content + old evidence_ref
    -> BLOCK

provider-evidenced generated_at <= freeze
    -> BLOCK

before/after hashes
    -> DERIVED BY EXECUTOR

verification plan
    -> DERIVED FROM FROZEN CONTRACT

provenance
    -> FROM VERIFIED GENERATION EVIDENCE + REQUEST/FROZEN/SOURCE BINDINGS

provider effect capability
    -> NONE
```

The terminal transition for this stage is exactly:

```text
AUTHORIZED_AND_FROZEN -> SolutionProvider -> ValidatedSolutionProposal
```
