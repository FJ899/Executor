# Executor Product Runtime Contract

Status: CURRENT PRODUCT PATH

## Canonical front door

The supported product entrypoint is `creative-os-product`.

`creative-os-executor` remains the generic/legacy foundation and historical proof CLI. Its GitHub-only pilot commands are not the product front door and must not be used to bypass Formation.

Canonical product flow:

```text
USER REQUEST
  -> RequestToContract001
  -> validated formation draft
  -> exact canonical GitHub request payload
  -> system publication of that exact payload (no manual rewrite)
  -> verified HUMAN ACCEPT / MODIFY / REJECT
  -> AUTHORIZED_AND_FROZEN
  -> SolutionProvider / ExternalIntelligence (zero effect authority)
  -> ValidatedSolutionProposal
  -> PilotRuntime technical execution
  -> ACTION_COMPLETED_REVIEW_REQUIRED
  -> controlled commit
  -> observed draft branch publication
  -> observed draft PR creation
  -> HUMAN REVIEW / ACCEPTANCE remains separate
```

## Decision lifecycle

- `ACCEPT` freezes the exact draft/request/authority evidence.
- `MODIFY` does not execute. It requires a new Formation revision, validation, publication and new human decision.
- `REJECT` is terminal and non-executable.

## State ownership

`PilotRuntime` is the active product lifecycle engine.

`RunStore` is `LEGACY_GENERIC_COMPATIBILITY_ONLY`. It is not a second product lifecycle engine and it no longer defines a `PASS` state. Historical records that contain the text `PASS` remain historical evidence only; they are not silently reinterpreted as current runtime state.

Active state is factored into independent axes:

- technical execution;
- technical result (`SUCCEEDED`, `BLOCKED`, `FAILED`, `STALE`, `UNKNOWN`);
- review state;
- human acceptance;
- consequential effect state.

`ACTION_COMPLETED_REVIEW_REQUIRED` means technical execution succeeded and human review is required. It is not Human acceptance and is not a merge authorization.

## Solution authority

A `SolutionProvider` receives an exact frozen contract and may return only `executor-solution-candidate/1.0` data.

Executor creates provider provenance at the boundary and validates the resulting proposal. Provider authority is always `effect_capability = NONE`.

## Consequential GitHub effects

The only publication effects authorized by the current product path are:

1. Formation authority issue publication in `FJ899/Executor`.
2. Draft branch publication in the frozen target repository.
3. Draft pull request creation in the frozen target repository.

There is no product effect slot for merge, deploy, release or tag.

Every provider write follows:

```text
VERIFY
-> RESERVE
-> CONSUME
-> durable PRE-WRITE ATTEMPT
-> EFFECT exactly once
-> fresh provider OBSERVE
-> BIND RESULT
```

Unknown write outcomes are never retried blindly. Timeout, provider 5xx, missing receipt, process interruption after the write, or incomplete observation require reconciliation before any new authority can be used.

The current recovery model distinguishes these cases explicitly:

- provider effect may have happened, receipt missing -> observe first; never repeat the write automatically;
- provider/global result bound but local result unbound -> bind only the missing local result;
- timeout or GitHub 5xx after send -> treat the outcome as ambiguous until fresh read-back;
- restart between write and binding -> recover from the exact durable pre-write attempt and frozen effect hash; `external_write_repeated = false`;
- complete provider absence -> the spent authority is not reused; any later attempt requires new authority.

## Publication authority keys

Keys are derived from frozen identities, never from an operator-controlled retry counter:

- `formation:<formation-draft-sha>:CREATE_AUTHORITY_ISSUE`
- `draft-pr:<frozen-contract-sha>:PUSH_DRAFT_BRANCH`
- `draft-pr:<frozen-contract-sha>:CREATE_DRAFT_PR`

This bounds each external mutation to one exact frozen request/contract and prevents a new `run_id` from manufacturing another consequential write.

## Workflow separation

`governance/WORKFLOW_CLASSIFICATION.json` is the source of truth for active-vs-historical workflow classification.

`p4-real-pilots-one-shot.yml`, run94 workflows, and exact-ref proof harnesses are historical evidence and are not callable product runtime dependencies.

The current product trust profile is `trust_profiles/github-product-gp001.json`; historical P4 trust profiles are not reused as product profiles.

## Explicit current non-goals

No multi-user model, additional task classes, generalized provider plugin system, new sandbox backend, multi-language execution runtime, merge automation, deploy automation, release automation or tag automation is authorized by this contract.
