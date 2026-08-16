# P4 GitHub Pilot Operator Guide

This guide describes the bounded product path selected in `PHASE_B_AUTHORIZATION.md`. GitHub is the governed intake and decision domain; the sandbox worker receives no GitHub token, network access or merge authority.

## 1. Publish the exact request

Create an issue in `JTJ07/Executor` whose body is exactly one prepared JSON file:

- `evidence/p4/requests/scriptops-request.json`;
- `evidence/p4/requests/reconstructor-request.json`.

The issue must be authored directly by the allowed GitHub user in `trust_profiles/github-p4-pilots.json`. Agent-generated or edited evidence is not a substitute for the direct actor event.

Verify and form the draft:

```bash
creative-os-executor github-pilot-draft \
  --profile trust_profiles/github-p4-pilots.json \
  --issue ISSUE_NUMBER
```

The command fetches the current issue and target commit from GitHub, verifies actor, repository association, exact body, expiry and `commit -> tree`, then prints a non-executable draft and `draft_sha256`.

## 2. Publish one exact decision

Post one unedited issue comment with this shape:

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
  "issued_at": "RFC3339_UTC_MATCHING_COMMENT_CREATION",
  "expires_at": "RFC3339_UTC_NO_MORE_THAN_60_MINUTES_LATER",
  "nonce": "UNIQUE_SAFE_VALUE"
}
```

`MODIFY` and `REJECT` are legal but never executable. Edited comments, another actor, another issue, changed request body, changed draft, stale/expired evidence or replay fail closed.

Consume the decision:

```bash
creative-os-executor github-pilot-decide \
  --profile trust_profiles/github-p4-pilots.json \
  --issue ISSUE_NUMBER \
  --comment COMMENT_ID \
  --ledger .executor/authority.sqlite3 > frozen.json
```

## 3. Bind external Intelligence without granting authority

Materialize the prepared external candidate only after freeze:

```bash
creative-os-executor materialize-pilot-proposal \
  --candidate evidence/p4/candidates/REPOSITORY-solution-candidate.json \
  --frozen frozen.json > proposal.json
```

The candidate cannot carry approval, network, secrets, merge or deploy fields. The materialized proposal is bound to the exact frozen contract, source commit/tree, allowed paths and before/after hashes.

## 4. Execute and publish only a draft PR

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

The runtime requires the approved counterexample to fail before mutation, atomically consumes one AAP, applies only exact replacement hashes, runs postcondition and regressions without network/secrets, checks scope and emits a report, patch and `executor-draft-pr-request/1.0`.

The trusted controller may then create the exact branch, commit and draft PR described by the result. It must not merge, deploy or publish a release.

## Terminal states

- `ACTION_COMPLETED_REVIEW_REQUIRED` — effect and evidence exist; human review is still required.
- `BLOCKED` — authority, identity, precondition or policy gate did not permit an effect.
- `FAILED` — execution began but objective evidence did not pass.

No runtime result equals product acceptance or Phase C PASS.
