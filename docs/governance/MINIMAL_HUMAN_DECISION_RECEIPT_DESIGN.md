---
document: "Minimal Human Decision Receipt Design"
version: "0.5"
status: "AUTHORITY CONTEXT OWNERSHIP REVIEW / IMPLEMENTATION BLOCKED"
date: "2026-08-09"
scope: "human decision record, canonical authority policy identity, external evidence and freeze verification"
repository: "litrgratis-pixel/Executor"
---

# Minimal Human Decision Receipt Design v0.5

```text
HUMAN DECISION RECEIPT != VERIFIED AUTHORITY EVIDENCE
AUTHENTICATION != AUTHORIZATION
AUTHORIZATION != DELEGATION
AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP
VALID POLICY CONTENT != CANONICAL POLICY AUTHORITY
LOWER TRUST MAY NOT WEAKEN HIGHER TRUST
```

## 1. End-to-end authority boundary

```text
USER REQUEST
    ↓
FORMATION KERNEL
    creates exact draft + review + decision request
    ↓
CANONICAL AUTHORITY REQUIREMENT RESOLUTION
    derives requirements from verified superior sources
    ↓
HUMAN DECISION ADAPTER
    records human action; DOES NOT prove authority
    ↓
HUMAN DECISION RECEIPT
    records WHO / WHAT / exact bound identities
    ↓
EXTERNAL AUTHORITY EVIDENCE
    proves actor + required authority context independently
    ↓
FREEZE GATE
    re-verifies canonical sources
    resolves effective requirement
    verifies evidence + exact identities
    ↓
AUTHORIZED_AND_FROZEN
```

No component may silently combine contract interpretation, authority-policy ownership, decision capture, external IAM ownership, evidence verification and freeze.

## 2. Existing Executor trust hierarchy is the root for requirement ownership

`EXECUTOR_POLICY.yaml` already establishes:

```text
executor_policy
> project_contract
> task_contract
> authoritative_source
> untrusted_repository_data
> generated_data
```

The design must reuse this hierarchy rather than inventing a parallel authority-policy store.

For the current Executor project, `project_contracts/executor-self.yaml` already identifies `EXECUTOR_POLICY.yaml` as an `authoritative_instruction`, and semantic changes to that policy are USER-owned.

Therefore the current GP001 authority boundary can reuse existing verified project/policy identity machinery.

## 3. Authority requirement != authority ownership

Executor may know:

```text
WHAT authority evidence is required
WHICH evidence verifier/profile is acceptable
WHICH exact transition the proof applies to
```

without owning:

```text
WHO currently holds the external role
WHO belongs to an organization
WHO has current IAM permissions
```

External authority systems own mutable role/identity truth.

Executor owns only the canonical requirement for the governed transition.

## 4. Requirement ownership by trust layer

```text
EXECUTOR_POLICY
    system-wide trust hierarchy and non-bypassable minima
        ↓
PROJECT_CONTRACT / superior project governance
    project/domain-specific authority requirements
        ↓
TASK CONTRACT
    may carry/reference/add narrower constraints
    cannot delete or replace superior constraints
        ↓
FORMATION PROFILE
    process configuration / reference only
    not an independent authority owner
```

Formation code, model output and caller arguments may not choose a weaker authority class or evidence source.

## 5. Conjunctive requirement composition

Authority is not modeled as a simple LOW/MEDIUM/HIGH scalar.

All applicable superior constraints survive:

```text
EFFECTIVE AUTHORITY REQUIREMENT
=
SYSTEM REQUIREMENTS
AND PROJECT REQUIREMENTS
AND VALID ADDITIONAL TASK-SPECIFIC REQUIREMENTS
```

Lower layers may add constraints.

They may not remove or override superior constraints.

No `last-write-wins` authority semantics are allowed.

## 6. Canonical authority policy source identity

A policy or project contract is authoritative because of both content and origin.

Minimum canonical source binding:

```text
repository
commit
path
blob/content sha256
source role
trust layer
```

For the current controlled Executor slice, the authority requirement should be resolved from files tracked at the exact verified Executor commit already bound by formation.

A mutable worktree copy is not authority.

An untracked file is not authority.

A caller-selected alternate repository is not authority.

A copied policy with valid syntax is not authoritative merely because its contents look plausible.

Core invariant:

> **VALID POLICY CONTENT != CANONICAL POLICY AUTHORITY.**

## 7. Authority requirement identity

The effective resolved requirement is a small immutable verification object, not an IAM database.

Minimum semantics:

```text
schema_version
authority_requirement_id
required_authority_classes[]
trusted_evidence_profiles[]
required_context_keys[]
source_bindings[]:
  trust_layer
  repository
  commit
  path
  content_sha256
  source_role
executor_commit
```

Canonical serialization yields:

```text
authority_requirement_sha256
```

The hash is bound into review material, decision request, Human Decision Receipt and freeze verification state.

## 8. Human Decision Receipt

The receipt records a decision fact, not an entitlement.

Minimum semantics:

```text
schema_version
receipt_id
decision_request_id
decision_request_sha256
actor_subject
authority_evidence_refs[]
decision: ACCEPT | MODIFY | REJECT
reviewed_contract_sha256
review_material_sha256
authority_requirement_sha256
formation_profile_sha256
canonical_task_sha256
executor_commit
decision_event_id
observed_at
freshness_id
```

Receipt fields do not become trusted permissions merely by existing.

## 9. External authority evidence

```text
DECISION FACT != AUTHORITY TO MAKE THAT DECISION
```

Evidence must independently establish the facts demanded by the canonical requirement:

```text
verified actor subject
verified issuer / trust owner
verified authority class/context
binding to decision event/request
freshness / validity required by the trusted evidence profile
```

Freeze Gate compares this evidence to the resolved requirement.

It never asks the receipt what authority should have been required.

## 10. F-7 — Authority Substitution

Failure:

```text
correct requirement
+ wrong actor/account/organization/context accepted as equivalent
```

Invariant:

```text
"SOME HUMAN APPROVED" != "THE REQUIRED AUTHORITY APPROVED"
AUTHORITY IDENTITY MUST BIND TO EXACT DECISION CONTEXT
```

## 11. F-8 — Authority Requirement Injection / Downgrade

Failure:

```text
superior policy requires A
    ↓
caller/model/task/formation injects weaker or different B
    ↓
real actor valid for B approves
    ↓
B is honestly verified
    ↓
freeze
```

Invariant:

```text
AUTHORITY REQUIREMENT MUST COME FROM CANONICAL SUPERIOR SOURCES
CALLER/MODEL MAY NOT SELECT OR DOWNGRADE IT
LOWER TRUST MAY NOT OVERRIDE HIGHER TRUST
MISSING REQUIRED SOURCE = FAIL CLOSED
```

## 12. F-9 — Authority Policy Source Substitution

Failure:

```text
system expects project/policy source S
        ↓
caller supplies structurally valid alternate S2
        ↓
S2 defines an acceptable-looking requirement
        ↓
Freeze Gate validates content but not canonical origin
        ↓
freeze
```

Examples:

```text
correct policy path from wrong repository
correct file from wrong commit
copied policy from mutable workspace
untracked replacement file
same schema under attacker-selected path
valid project contract pointing at attacker-selected policy
```

This differs from F-8:

```text
F-8:
wrong requirement value/composition

F-9:
wrong authority-policy source accepted as canonical
```

Invariants:

```text
AUTHORITY POLICY SOURCE MUST BIND TO EXACT REPOSITORY + COMMIT + PATH + CONTENT IDENTITY
CALLER MAY NOT SELECT THE CANONICAL POLICY OR PROJECT CONTRACT SOURCE
MUTABLE WORKSPACE CONTENT != CANONICAL AUTHORITY SOURCE
```

## 13. Requirement and policy drift

Any canonical policy or requirement change after review invalidates the previous decision for freeze.

```text
source/policy A
    ↓
human reviews and ACCEPTS
    ↓
source/policy becomes B
    ↓
old receipt reused
```

must fail.

Required transition:

```text
policy/source change
 -> new source binding
 -> new authority_requirement_sha256
 -> new review_material_sha256
 -> new decision_request_sha256
 -> previous decision stale
 -> new human review required
```

## 14. Exact Freeze Gate algorithm — design semantics

Only `ACCEPT` may be freeze-eligible.

Freeze Gate must independently:

```text
1. resolve expected Executor/project canonical source identities from the already-verified formation state;
2. verify repository + exact commit identities;
3. verify tracked policy/project-contract files at those commits;
4. verify content/blob hashes and source roles;
5. resolve all applicable authority requirements in trust order;
6. compose them conjunctively without lower-level deletion;
7. recompute authority_requirement_sha256;
8. compare it with the review/request/receipt binding;
9. verify every required external authority evidence profile/class/context;
10. verify exact actor subject binding;
11. verify exact decision-request identity;
12. verify exact review-material identity;
13. verify exact current draft identity == contract to be frozen.
```

It may not accept a precomputed requirement or policy source solely because the caller supplied a valid-looking object.

Any missing or mismatched superior source:

```text
AUTHORIZED_AND_FROZEN = FORBIDDEN
```

## 15. Freeze Gate is not IAM and not policy owner

Freeze Gate may know:

```text
canonical source identities
required authority class identifiers
trusted evidence profile identifiers
verification rules
```

It must not own:

```text
users
organization membership
role assignments
enterprise permissions
standing delegation
```

It also must not author the authority policy it verifies.

## 16. Replay

No global one-time receipt-consumption ledger is introduced.

```text
same receipt + different source/requirement/request/contract/review identity = INVALID
same receipt + same immutable identities + still-valid evidence = same authorization fact
```

Same-identity verification is idempotent, not new authority.

## 17. Required adversarial cases before implementation

At minimum:

1. caller-forged Human Decision Receipt;
2. fabricated authority evidence reference;
3. valid login without required authority;
4. Human A receipt + Human B evidence;
5. correct actor in wrong authority context;
6. caller injects weaker authority requirement;
7. model proposes weaker requirement;
8. task deletes superior requirement;
9. formation profile invents authority requirement;
10. lower layer replaces rather than conjunctively adds;
11. missing source defaults permissively;
12. wrong project contract repository;
13. wrong project contract commit;
14. copied/dirty/untracked authority-policy file;
15. correct policy filename from wrong path/repository;
16. caller-selected alternative evidence profile;
17. canonical source changes after human review;
18. wrong authority-requirement hash in receipt;
19. correct evidence for wrong authority class/context;
20. wrong request/review/contract identity;
21. stale approval after draft mutation;
22. old approval generalized as standing trust;
23. `REJECT` -> `ACCEPT` substitution;
24. `MODIFY` executed without new review;
25. decision adapter certifies own evidence;
26. Freeze Gate authors or selects its own weaker policy.

Expected:

```text
FAIL CLOSED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 18. Current adversarial-review findings

```text
R-1 Authorization Receipt was too strong
 -> Human Decision Receipt

R-2 adapter role was too broad
 -> decision capture separated from authority evidence

R-3 receipt self-described bounded authority
 -> boundedness moved to exact verifier semantics

R-4 authority substitution was implicit
 -> F-7 explicit

R-5 authority context ownership ambiguous
 -> requirement separated from external authority ownership

R-6 valid weak approval could pass after requirement injection
 -> F-8 explicit

R-7 requirement could drift after review
 -> requirement identity bound into full review/decision chain

R-8 formation profile looked like authority owner
 -> rejected; it is below existing executor_policy/project_contract trust hierarchy

R-9 override composition could erase superior constraints
 -> conjunction required

R-10 canonical project/policy source itself could be substituted
 -> F-9 explicit; source binds repo + commit + path + content identity

R-11 existing project-bundle validation can be reused
 -> no new AuthorityPolicyStore / second policy root is justified
```

F-7, F-8 and F-9 must be reconciled into PR #51 before #51 is ever merged.

## 19. Authority Context Ownership Review — current result

Provisional ownership is now explicit:

```text
EXECUTOR_POLICY
  owns system trust hierarchy / system minima

PROJECT_CONTRACT or equivalent superior project governance
  owns project/domain authority requirements

TASK / FORMATION
  consume/reference/add constraints
  cannot weaken or redefine superior policy

EXTERNAL AUTHORITY SYSTEM
  owns mutable truth about who currently possesses authority

HUMAN DECISION RECEIPT
  records the exact decision event

FREEZE GATE
  verifies canonical source identity + effective requirement + external evidence
  owns neither IAM membership nor authority policy
```

For current GP001, canonical authority-policy material can be read from the same exact verified Executor commit already bound by formation, using the repository/project verification mechanisms already present in Executor.

## 20. Next design question

Implementation remains blocked.

The Authority Context Ownership question is substantially answered.

The next unresolved issue is now the **external evidence trust adapter**:

> How does Freeze Gate verify `authority_evidence_ref` from an approved external authority system without letting the decision adapter or caller choose the verifier/issuer at runtime?

This must be solved as another bounded design problem, not by embedding a full IAM system into Executor.
