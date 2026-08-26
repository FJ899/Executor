---
document: "SOLUTION_PROVIDER_001"
version: "0.3"
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
POST-FREEZE GENERATION CHALLENGE
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

That validator requires the successful terminal `CONTRACT_ACCEPT` receipt. A caller-provided object that merely claims `AUTHORIZED_AND_FROZEN` is insufficient.

Before generation, Executor also recomputes the exact frozen contract hash.

## Important time semantics

`authority_snapshot.verified_at` is the final live-verification cutoff. It is **not** the instant at which `AUTHORIZED_AND_FROZEN` is created.

The lifecycle is:

```text
FINAL LIVE VERIFY
    -> immutable authority snapshot
    -> CONTRACT_ACCEPT consumption
    -> durable result binding
    -> terminal frozen result validates as AUTHORIZED_AND_FROZEN
```

Stage 2 therefore does not use `authority_snapshot.verified_at` as the freeze timestamp.

Instead, after `validate_frozen_pilot_authority()` has successfully proved the terminal frozen result and after exact source verification, `SolutionProvider` creates a fresh post-freeze generation challenge:

```text
schema_version: executor-solution-generation-challenge/1.0
nonce: cryptographically random 256-bit value
issued_at: Executor UTC timestamp captured after frozen validation
```

The challenge is included in the exact prompt identity. Provider generation evidence must bind the prompt hash and its provider-evidenced `generated_at` must strictly postdate `challenge.issued_at`.

This is a conservative post-freeze lower bound: the challenge cannot be issued until the terminal frozen result has already validated. Therefore a cached response produced in the interval between final live verification and actual freeze cannot satisfy the challenge timestamp and prompt binding.

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

The generator receives a deterministic frozen task/source payload plus one fresh non-deterministic post-freeze challenge.

The prompt binds:

- frozen contract hash;
- frozen target;
- frozen task;
- exact bounded source context;
- fresh generation challenge nonce;
- challenge issuance timestamp;
- explicit no-effect output contract.

The generator may return only:

```text
schema_version
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
- source-context hash;
- prompt hash;
- challenge identity;
- before/after hashes;
- evidence plan;
- proposal identity;
- authorization/effect metadata.

Attempted scope expansion or additional mutation metadata fails closed.

## Independent generation-evidence boundary

Raw generator content is not itself generation evidence.

The adapter returns an `evidence_ref`. A separate read-only `SolutionGenerationVerifier` resolves that reference into immutable provider evidence for the exact generation event.

Verified evidence must bind:

```text
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

Executor computes the canonical SHA-256 of the exact returned generation content and requires it to equal the independently verified `response_sha256`.

The verified `prompt_sha256` necessarily covers the fresh post-freeze generation challenge.

Executor also requires:

```text
provider-evidenced generated_at > generation_challenge.issued_at
```

A cached response/evidence from before freeze, from another invocation, or from the same frozen contract but an earlier challenge cannot be rebound to the current invocation.

## Executor-owned bindings

For each accepted generator mutation Executor derives:

```text
expected_before_sha256 = SHA256(exact verified frozen-source bytes)
expected_after_sha256  = SHA256(generator replacement UTF-8 bytes)
```

Executor also derives:

- repository, commit and tree from the frozen context;
- verification plan from frozen `postcondition_argv` and `regression_argv`;
- deterministic proposal id from frozen/context/prompt/challenge/generation binding;
- provenance from independently verified provider generation evidence.

The result is passed through the existing `materialize_solution_candidate()` and `validate_solution_proposal()` path. Stage 2 does not create a parallel proposal validator.

## Provenance

Stage 2 uses:

```text
executor-solution-provenance/1.3
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
- post-freeze generation challenge SHA-256;
- challenge issuance timestamp;
- independent generation evidence reference;
- exact generation response SHA-256;
- generation verification method;
- `human_solution_edits = 0`;
- `effect_capability = NONE`;
- derivation `GENERATED_AFTER_POST_FREEZE_CHALLENGE`.

`validate_solution_proposal()` requires the persisted provider `generated_at` to postdate the persisted post-freeze challenge time. It does not mislabel `authority_snapshot.verified_at` as the freeze instant.

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
challenge issued at/before final live verification
provider-evidenced generated_at at/before post-freeze challenge
cached response from an earlier challenge
cross-contract/source/context/prompt replay
changed response content under stale evidence_ref
source/request/frozen/context/prompt binding mismatch
invalid after hash
missing frozen verification commands
attempted effect-authority metadata
```

## Historical P4 blocker and remediation

Historical head `7fd0414c559a2890760e30031abf7a71d6b12e5f` was fail-open because Executor assigned current bindings and a fresh timestamp after receiving arbitrary raw generator content.

Head `0cecd41bc20b770b4f8d01ae6938ea69c6cb54b7` removed that timestamp fabrication and introduced independent generation evidence, but P4 correctly found a remaining gap: provider `generated_at` was compared to `authority_snapshot.verified_at`, which precedes successful `CONTRACT_ACCEPT` result binding.

The current remediation does **not** substitute `decision_consumption.consumed_at`, because consumption also occurs before durable result binding.

Instead the provider invocation is challenged only after the full frozen result has passed `validate_frozen_pilot_authority()`. The challenge is fresh, unpredictable, prompt-bound and timestamped after that terminal validation. Accepted provider evidence must postdate and bind that exact challenge.

This directly blocks the previously open interval:

```text
final live verification < stale generated_at <= actual freeze
```

because such evidence necessarily predates the post-freeze challenge and/or binds a different prompt.

## Effect boundary

The solution generator receives no Executor ledger, runtime, sandbox mutation handle, GitHub write client or action-authorization handle.

Stage 2 result remains effect-free:

```text
effect_capability: NONE
status: VALIDATED_SOLUTION_PROPOSAL
```

A valid proposal is not execution authority.

`PilotRuntime` remains unchanged. Runtime command authority continues to come only from frozen `precondition_argv`, `postcondition_argv` and `regression_argv`; proposal `evidence_plan` is evidence metadata, not command authority.

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
valid terminal frozen authority + exact source
    -> issue fresh post-freeze generation challenge

provider generation bound to exact challenge prompt
    + independent exact response evidence
    + generated_at > challenge.issued_at
    -> ValidatedSolutionProposal

invalid/fabricated frozen authority
    -> BLOCK BEFORE CHALLENGE

wrong repo/commit/tree or dirty source
    -> BLOCK BEFORE GENERATOR

cached response from pre-freeze or prior invocation
    -> BLOCK

provider generated_at <= post-freeze challenge
    -> BLOCK

out-of-scope generator mutation
    -> BLOCK

generator tries to control Executor-owned hashes/metadata
    -> BLOCK

before/after hashes
    -> DERIVED BY EXECUTOR

verification plan
    -> DERIVED FROM FROZEN CONTRACT

provider effect capability
    -> NONE
```

The terminal transition for this stage remains exactly:

```text
AUTHORIZED_AND_FROZEN -> SolutionProvider -> ValidatedSolutionProposal
```
