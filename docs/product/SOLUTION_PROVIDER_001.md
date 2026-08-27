---
document: "SOLUTION_PROVIDER_001"
version: "0.4"
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

## Important time and causal semantics

`authority_snapshot.verified_at` is the final live-verification cutoff. It is **not** the instant at which `AUTHORIZED_AND_FROZEN` is created.

The lifecycle is:

```text
FINAL LIVE VERIFY
    -> immutable authority snapshot
    -> CONTRACT_ACCEPT consumption
    -> durable result binding
    -> terminal frozen result validates as AUTHORIZED_AND_FROZEN
```

Stage 2 therefore does not use `authority_snapshot.verified_at` or `decision_consumption.consumed_at` as the freeze timestamp.

Instead, after `validate_frozen_pilot_authority()` has successfully proved the terminal frozen result and after exact source verification, `SolutionProvider` computes the SHA-256 of the exact terminal `decision_consumption` receipt and creates a fresh post-freeze generation challenge:

```text
schema_version: executor-solution-generation-challenge/1.0
nonce: cryptographically random 256-bit value
issued_at: Executor UTC timestamp captured after frozen validation
freeze_receipt_sha256: SHA256(exact terminal decision_consumption)
```

The exact challenge is included in the prompt identity. Independent provider generation evidence must bind the exact prompt, challenge identity and terminal freeze-receipt identity.

The random challenge plus terminal receipt binding is the causal proof that the accepted generation belongs to a post-freeze invocation. The timestamp rule:

```text
provider generated_at > generation_challenge.issued_at
```

is an additional sanity check, not a substitute for that causal binding.

A cached response produced in the interval between final live verification and actual freeze cannot bind a challenge containing the terminal receipt that did not yet exist.

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
- exact terminal freeze-receipt SHA-256;
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
- terminal freeze-receipt identity;
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
generation_challenge_sha256
generation_challenge_issued_at
freeze_receipt_sha256
verification_method
```

Executor computes the canonical SHA-256 of the exact returned generation content and requires it to equal the independently verified `response_sha256`.

The verified prompt/challenge/receipt tuple makes pre-freeze or cross-invocation rebinding fail closed.

## Structural validation is not authoritative generation verification

`materialize_solution_candidate()` and `validate_solution_proposal()` remain the shared structural proposal boundary. They validate schema, frozen bindings, scope, hashes, provenance shape and verification-plan requirements.

They are intentionally **not** proof that an external provider record exists.

A structural `ValidatedSolutionProposal` may therefore be useful for pure validation/tests, but it may not cross an effect boundary by itself.

Before an existing runtime can consume a proposal, `validate_authoritative_solution_proposal()` must:

1. revalidate the complete frozen authority;
2. recompute the exact terminal `decision_consumption` SHA-256;
3. structurally validate the proposal;
4. independently resolve `generation_evidence_ref` through `SolutionGenerationVerifier`;
5. require exact evidence/proposal agreement for provider, model, generation time, frozen contract, source, context, prompt, challenge, response and verification method;
6. require exact terminal freeze-receipt binding;
7. reconstruct the canonical generator response from the validated mutations/rationale and independently recompute its response hash.

This prevents caller-created provenance strings/hashes from becoming authoritative merely because they are mutually consistent.

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

The result is passed through the existing `materialize_solution_candidate()` and `validate_solution_proposal()` structural path. Stage 2 does not create a competing structural validator.

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

The terminal freeze-receipt hash is independently re-established from `frozen_result` and from the provider evidence rather than trusted from caller provenance.

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
missing provider generation record
provider evidence/provenance mismatch
terminal freeze-receipt mismatch
reconstructed response hash mismatch
invalid after hash
missing frozen verification commands
attempted effect-authority metadata
runtime consumption without independent generation verifier
```

## Historical P4 blockers and remediation

The first P4 failure found that Executor could assign current bindings and a fresh timestamp after receiving arbitrary raw generator content. That was replaced by independently verified generation evidence bound to provider/model/time/frozen/source/context/prompt/response.

The second P4 failure found a remaining temporal gap: provider `generated_at` was compared to `authority_snapshot.verified_at`, which precedes successful `CONTRACT_ACCEPT` result binding. That was replaced by a post-terminal-freeze challenge whose prompt also binds the terminal receipt identity.

The third P4 failure found that this protection existed only on the `SolutionProvider` production path. `validate_solution_proposal()` remained structural and the existing `PilotRuntime` consumed its result directly, so caller-fabricated but structurally consistent provenance could bypass `SolutionGenerationVerifier`.

The current remediation closes the **consumer** side as well. `PilotRuntime` now refuses a proposal unless a trusted `SolutionGenerationVerifier` is supplied and `validate_authoritative_solution_proposal()` successfully re-reads and binds the exact provider evidence. No verifier or missing/mismatched evidence is a hard block before policy loading or any effect authorization.

All historical FAIL results remain valid for their audited SHAs; later remediation does not overwrite them.

## Effect boundary

The solution generator receives no Executor ledger, runtime, sandbox mutation handle, GitHub write client or action-authorization handle.

Stage 2 result remains effect-free:

```text
effect_capability: NONE
status: VALIDATED_SOLUTION_PROPOSAL
```

A valid proposal is not execution authority.

Stage 2 does not add a new runtime/effect capability. It hardens the already-existing `PilotRuntime` entry boundary so structural-only proposal validation cannot authorize existing effects. Runtime command authority continues to come only from frozen `precondition_argv`, `postcondition_argv` and `regression_argv`; proposal `evidence_plan` is evidence metadata, not command authority.

The legacy/raw `run-pilot` composition has no trusted generation-verifier adapter in Stage 2; absent such a trusted dependency, runtime fails closed. Stage 2 does not invent a caller-supplied or file-supplied verifier substitute.

## Non-goals

This stage does not implement:

- a new mutation-application capability;
- a new sandbox-execution capability;
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
    -> issue fresh post-freeze generation challenge bound to terminal receipt

provider generation bound to exact challenge prompt
    + independent exact response evidence
    + generated_at > challenge.issued_at
    -> structurally ValidatedSolutionProposal

structural proposal + trusted generation verifier
    + exact provider record
    + exact terminal freeze receipt
    + independently reconstructed response hash
    -> eligible for authoritative runtime consumption

structural proposal without generation verifier
    -> BLOCK BEFORE RUNTIME EFFECT BOUNDARY

fabricated provenance with no provider record
    -> BLOCK

provider record with wrong terminal receipt/challenge/response
    -> BLOCK

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

Any later effect-capable consumer must independently re-establish the provider-evidence binding before using that proposal.