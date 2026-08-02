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

> Is this exact action, against this exact run state and these exact immutable inputs, eligible for one atomic authorization consumption under the current policy?

The packet is not a plan, recommendation, model opinion or replacement for the task contract. It is a one-time capability bound to a concrete action.

## Mandatory bindings

Every packet binds:

- run ID;
- task ID, risk class and mode;
- Executor commit;
- hashes of the Executor policy, project contract, task contract and test contract;
- all repository commit locks;
- exact action kind, argv, paths and requested capabilities;
- issuer role, issuer identity and externally verified evidence reference;
- issue and expiry time;
- one-use constraint;
- canonical payload hash.

Any mismatch, expiry, replay, path expansion, capability expansion, unknown field, issuer-evidence mismatch or integrity failure blocks the action.

## Issuer evidence boundary

A packet cannot prove its own issuer.

The active authorization context must contain a verifier-produced binding from `evidence_ref` to the exact issuer role and issuer ID. A self-declared `USER` or `POLICY_VERIFIER` string is insufficient and must fail closed.

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

The packet authorizes only the declared kind. It does not imply permission for a later, broader or differently parameterized action.

## Merge boundary

`MERGE_PULL_REQUEST` always requires:

- a verified `USER` issuer;
- `manual_confirmation_required: true`;
- `max_uses: 1` as an integer, never a boolean alias;
- an unexpired packet bound to the exact run, contracts and repository commits.

This is explicit manual authorization. It does not enable auto-merge and does not weaken `EXECUTOR_POLICY.yaml execution.auto_merge=false`.

## External execution boundary

`EXTERNAL_PROJECT_EXECUTION` requires both:

- `EXECUTOR_POLICY.yaml execution.external_projects=true` in the bound policy snapshot;
- a verified `USER`-issued packet with `external_project: true`.

The packet cannot override a policy denial.

## One-time consumption

Validation proves only that a packet is structurally and semantically eligible for atomic consumption in the active context.

Execution additionally requires an authorization ledger transaction that atomically:

1. proves the packet ID has not been consumed;
2. records the payload hash and action binding;
3. marks the packet consumed before the consequential action begins;
4. binds the action result to that consumption event.

Reusing an already consumed `packet_id` is `AUTHORIZATION_REPLAY` and must fail closed.

The ledger and state-machine consumption gate are implemented as part of the M3 design. Until that integration is present and verified, a valid packet must be reported as `READY_FOR_ATOMIC_CONSUMPTION`, never as proof that an action was executed.

## Relationship to M3

M3 replayable evidence must record:

- the validated packet payload hash;
- the verified issuer evidence binding;
- its atomic consumption event;
- the exact action result;
- the policy, contract and repository snapshots to which it was bound.

M3 may not invent, broaden, renew or retroactively create an authorization packet.
