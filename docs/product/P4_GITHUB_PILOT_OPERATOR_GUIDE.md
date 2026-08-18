# P4 GitHub Pilot Operator Guide

This guide describes the bounded product path selected in `PHASE_B_AUTHORIZATION.md`. GitHub is the governed intake and decision domain; the sandbox worker receives no GitHub token, network access or merge authority.

The authority model has two distinct stages:

```text
STAGE A — MUTABLE HUMAN AUTHORITY FORMATION
live request / ACCEPT
  -> FINAL LIVE VERIFY
  -> exact immutable authority snapshot
  -> global CONTRACT_ACCEPT consumption
  -> AUTHORIZED_AND_FROZEN only on success

STAGE B — CONSEQUENTIAL EFFECT
AUTHORIZED_AND_FROZEN snapshot + successful CONTRACT_ACCEPT receipt
  -> proposal / policy / preconditions
  -> effect AAP
  -> global effect reservation + provider-time freshness
  -> local consume
  -> mutation / evidence / result binding
```

A post-cutoff edit/delete of the original GitHub request/comment is not a retroactive revocation source for an already frozen contract.

## 1. Publish the exact request

Create an issue in `JTJ07/Executor` whose body is exactly one prepared request JSON for the authorized pilot objective.

The issue must be authored directly by the allowed GitHub user in `trust_profiles/github-p4-pilots.json`. Agent-generated or app-mediated evidence is not a substitute for the direct actor event.

Verify and form the reviewable draft:

```bash
creative-os-executor github-pilot-draft \
  --profile trust_profiles/github-p4-pilots.json \
  --issue ISSUE_NUMBER
```

The command fetches the current issue and target commit from GitHub, verifies actor, repository association, exact body, expiry and `commit -> tree`, then prints a non-executable draft and `draft_sha256`. Observation metadata such as `request_evidence.observed_at` is excluded from semantic draft-hash material, so repeated reads of one unchanged issue produce the same `draft_sha256`.

## 2. Publish one exact decision

Post one direct-human issue comment with this shape:

```json
{
  "schema_version": "executor-github-decision/1.0",
  "request": {
    "repository": "JTJ07/Executor",
    "issue_number": 0,
    "issue_node_id": "COPY_FROM_VERIFIED_DRAFT_EVIDENCE",
    "body_sha256": "COPY_FROM_VERIFIED_DRAFT_EVIDENCE"
  },
  "draft_sha256": "COPY_EXACT_DRAFT_SHA256",
  "decision": "ACCEPT",
  "valid_for_seconds": 3600,
  "nonce": "UNIQUE_SAFE_VALUE"
}
```

`MODIFY` and `REJECT` are legal but never executable. The provider's GitHub comment `created_at` is the decision timestamp; expiry is derived as `created_at + valid_for_seconds`, bounded by the trust profile. Edited decisions, wrong actor/origin, wrong issue, changed request binding, changed draft, stale/expired evidence or replay fail closed.

### Revocation cutoff and freeze

Consume the decision with:

```bash
creative-os-executor github-pilot-decide \
  --profile trust_profiles/github-p4-pilots.json \
  --issue ISSUE_NUMBER \
  --comment COMMENT_ID \
  --ledger .executor/authority.sqlite3 > frozen.json
```

`github-pilot-decide` performs an initial read to construct the reviewed draft/decision and then performs a **final live request + decision verification immediately before `CONTRACT_ACCEPT`**. The final read uses the same authoritative `verify_github_request(...)` and `verify_github_decision(...)` trust logic; there is no weaker second verifier.

The exact final provider evidence is snapshotted and hashed. Global `CONTRACT_ACCEPT` consumes that snapshot SHA-256. The snapshot contains, at minimum, exact request/decision provider identities, body hashes and payloads, immutable issue/comment IDs, direct-human provenance including the required `performed_via_github_app` signal, request/draft binding, decision edit/freshness evidence, and pinned target commit/tree evidence.

If final verification passes but global consumption fails, the command returns no frozen authority. Any retry starts with a new final live verification. A failed snapshot is not reusable authority.

Only successful `CONTRACT_ACCEPT` consumption plus durable result binding produces `AUTHORIZED_AND_FROZEN` with an embedded immutable authority snapshot and receipt relationship.

## 3. Bind external Intelligence without granting authority

Materialize the prepared external candidate only after freeze:

```bash
creative-os-executor materialize-pilot-proposal \
  --candidate evidence/p4/candidates/REPOSITORY-solution-candidate.json \
  --provenance evidence/p4/intelligence/REPOSITORY-provenance.json \
  --frozen frozen.json > proposal.json
```

The proposal is bound to the exact frozen contract, source commit/tree, allowed paths and before/after hashes. External Intelligence has no approval, network, secret, merge or deploy authority.

## 4. Execute from frozen authority

Resolve an immutable local Docker image ID and run:

```bash
creative-os-executor run-pilot \
  --profile trust_profiles/github-p4-pilots.json \
  --issue ISSUE_NUMBER \
  --comment COMMENT_ID \
  --frozen frozen.json \
  --proposal proposal.json \
  --ledger .executor/authority.sqlite3 \
  --workspace TARGET_CHECKOUT \
  --runs-root .executor/runs \
  --run-id UNIQUE_RUN_ID \
  --image sha256:EXACT_LOCAL_IMAGE_ID
```

At Stage B, `--issue` and `--comment` are exact frozen-evidence locators and must match the immutable contract. They are **not** instructions to restore mutable GitHub issue/comment currentness as authority. `run-pilot` validates the embedded authority snapshot, snapshot SHA, request/decision/draft/target bindings, direct-human evidence and successful FINAL local/global `CONTRACT_ACCEPT` receipts before it can construct effect authority.

The runtime then requires the approved counterexample to fail before mutation, atomically consumes one separate EFFECT AAP, enforces frozen decision `not_after` at effect reservation with provider-controlled `provider_created_at`, applies only exact replacement hashes, runs postcondition/regressions without network/secrets, checks scope/link safety and emits a report, patch and `executor-draft-pr-request/1.0`.

The trusted controller may create only the exact dedicated branch/commit/draft PR described by a legal result. It must not merge, deploy or publish a release.

## 5. Fresh P4 series operation

`.github/workflows/p4-real-pilots-one-shot.yml` is consequential and therefore manual `workflow_dispatch` only. It accepts six explicit comment IDs: three fresh direct-human ACCEPTs for ScriptOps and three for Reconstructor.

A PR synchronization must not run this workflow. Historical ACCEPT 001–012 are consumed/historical and must never be supplied as a new candidate's authority. The provider-backed one-shot namespace independently rejects replay, but operators must also obey the provenance rule.

The corrective revocation-cutoff change stops before fresh human authority. Do not dispatch the new six-run series until the human has supplied six fresh exact-head ACCEPT events.

## Terminal states

- `ACTION_COMPLETED_REVIEW_REQUIRED` — effect and evidence exist; human review is still required.
- `BLOCKED` — authority, identity, precondition or policy gate did not permit a legal effect.
- `FAILED` — execution began but objective evidence did not pass.

No runtime result equals P4, Phase C PASS, merge authorization or final human acceptance.
