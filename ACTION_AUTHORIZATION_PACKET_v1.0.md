# Action Authorization Packet v1.0

## Status

```text
PRODUCT DECISION
TERMINAL AUTHORIZATION CONTRACT
FROZEN BEFORE M3
```

## Purpose

The Executor may analyse, plan, validate and prepare work without an Action Authorization Packet. It may not cross the final boundary into a consequential action merely because earlier contracts are valid or tests pass.

The terminal packet answers one narrow question:

> Is this exact action, against this exact run state and these exact immutable inputs, authorized once under the current policy?

The packet is not a plan, recommendation, model opinion or replacement for the task contract. It is a one-time capability bound to a concrete action.

## Mandatory bindings

Every packet binds:

- run ID;
- task ID, risk class and mode;
- Executor commit;
- hashes of the Executor policy, project contract, task contract and test contract;
- all repository commit locks;
- exact action kind, argv, paths and requested capabilities;
- issuer identity and evidence reference;
- issue and expiry time;
- one-use constraint;
- canonical payload hash.

Any mismatch, expiry, replay, path expansion, capability expansion or integrity failure blocks the action.

## Issuers

Two issuer roles exist:

- `POLICY_VERIFIER` — may authorize only actions that remain inside already approved low/medium-risk, non-external, offline and secret-free boundaries;
- `USER` — required for high-risk work, external projects, network or secret access, and pull-request merge.

A model cannot issue a terminal packet in its own name and cannot convert its recommendation into user authorization.

## Action kinds

The closed v1 set is:

- `SANDBOX_EXECUTION`;
- `WRITE_REPOSITORY`;
- `CREATE_PULL_REQUEST`;
- `MERGE_PULL_REQUEST`;
- `EXTERNAL_PROJECT_EXECUTION`.

The packet authorizes only the declared kind. It does not imply permission for a later or broader action.

## Merge boundary

`MERGE_PULL_REQUEST` always requires:

- a `USER` issuer;
- `manual_confirmation_required: true`;
- `max_uses: 1`;
- an unexpired packet bound to the exact run and repository commits.

This is explicit manual authorization. It does not enable auto-merge and does not weaken `EXECUTOR_POLICY.yaml execution.auto_merge=false`.

## External execution boundary

`EXTERNAL_PROJECT_EXECUTION` requires both:

- `EXECUTOR_POLICY.yaml execution.external_projects=true` in the bound policy snapshot;
- a `USER`-issued packet with `external_project: true`.

The packet cannot override a policy denial.

## One-time consumption

Validation proves that a packet is well formed and matches the active context. Execution additionally requires atomic consumption in an authorization ledger. Reusing an already consumed `packet_id` is `AUTHORIZATION_REPLAY` and must fail closed.

The ledger and state-machine consumption gate are implemented separately from this contract freeze. Until that integration is present and verified, validation alone must not be presented as evidence that a consequential action was executed.

## Relationship to M3

M3 replayable evidence must record:

- the validated packet payload hash;
- its consumption event;
- the exact action result;
- the policy and repository snapshots to which it was bound.

M3 may not invent, broaden or renew an authorization packet.
