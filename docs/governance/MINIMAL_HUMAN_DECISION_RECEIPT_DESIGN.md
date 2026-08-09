---
document: "Minimal Human Decision Receipt Design"
version: "0.4"
status: "AUTHORITY CONTEXT OWNERSHIP REVIEW / IMPLEMENTATION BLOCKED"
date: "2026-08-09"
scope: "human decision record, canonical authority-requirement ownership, external evidence and freeze verification"
repository: "litrgratis-pixel/Executor"
---

# Minimal Human Decision Receipt Design v0.4

```text
HUMAN DECISION RECEIPT != VERIFIED AUTHORITY EVIDENCE
AUTHENTICATION != AUTHORIZATION
AUTHORIZATION != DELEGATION
AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP
LOWER-TRUST LAYER MAY NOT WEAKEN HIGHER-TRUST AUTHORITY REQUIREMENT
```

## 1. Boundary

```text
USER REQUEST
    ↓
FORMATION KERNEL
    creates exact draft + review + decision request
    ↓
CANONICAL AUTHORITY REQUIREMENT RESOLUTION
    derives requirements from superior trusted sources
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
    recomputes/resolves canonical requirement
    verifies evidence + exact current identities
    ↓
AUTHORIZED_AND_FROZEN
```

No component may silently combine contract interpretation, authority-requirement ownership, human decision capture, external authority ownership, evidence verification and freeze.

## 2. Existing Executor trust hierarchy constrains the design

`EXECUTOR_POLICY.yaml` already defines the trust order:

```text
executor_policy
project_contract
task_contract
authoritative_source
untrusted_repository_data
generated_data
```

Therefore a formation profile or generated decision record cannot become a new authority source merely because it is convenient for implementation.

The design must preserve the existing higher-level rule:

```text
LOWER TRUST CANNOT OVERRIDE HIGHER TRUST
```

## 3. Authority requirement versus authority ownership

Core invariant:

> **AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP.**

Executor may know:

```text
WHAT proof class is required
WHICH external evidence profile is acceptable
WHICH exact governed transition the requirement applies to
```

without owning:

```text
WHO currently holds that authority
WHO belongs to which organization
WHO has which external role or entitlement
```

The external authority system owns changing identity/role membership.

Executor owns only the canonical rule describing what evidence must be presented before a governed transition may occur.

## 4. Who may define the authority requirement?

Authority requirements must originate from already-trusted governance layers, not request-specific caller input.

Conceptual ownership:

```text
EXECUTOR_POLICY
    owns system-level trust hierarchy and non-bypassable minimum rules
        ↓
PROJECT_CONTRACT / equivalent superior project governance
    may define project/domain-specific authority requirements
        ↓
TASK_CONTRACT
    may carry or add narrower requirements
    may NOT remove superior requirements
        ↓
FORMATION PROFILE
    may reference / transport the resolved requirement
    is NOT an independent authority owner
```

The current `REQUEST_TO_CONTRACT_001` formation profile is therefore not sufficient, by itself, to establish a new authority class.

A profile can say:

```text
resolve authority requirement according to canonical policy X
```

It must not be able to say:

```text
for this request, LOW_RISK_APPROVER is enough
```

when a superior policy requires something else.

## 5. Requirement composition is conjunctive, not overriding

Authority classes are not assumed to form a simple numeric ladder.

Therefore the design does not use:

```text
LOW < MEDIUM < HIGH
```

as its security rule.

Instead, all applicable canonical superior requirements survive composition:

```text
EFFECTIVE AUTHORITY REQUIREMENT
    =
SYSTEM REQUIREMENT
AND
PROJECT REQUIREMENT
AND
ANY VALID NARROWER TASK-SPECIFIC REQUIREMENT
```

A lower layer may add another constraint.

It may never replace or delete a superior constraint.

Example:

```text
EXECUTOR_POLICY:
verified human authority required

PROJECT_CONTRACT:
production deployment approval required

TASK-SPECIFIC RULE:
service owner approval also required
```

Effective requirement:

```text
verified human authority
AND production deployment approval
AND service owner approval
```

not whichever requirement appeared last.

## 6. Canonical authority requirement identity

The resolved requirement is a small immutable verification object, not an IAM database.

Minimum semantics:

```text
schema_version
authority_requirement_id
required_authority_classes[]
trusted_evidence_profiles[]
required_context_keys[]
source_bindings[]:
  source_type
  source_identity
  source_sha256
executor_commit
```

Canonical serialization yields:

```text
authority_requirement_sha256
```

Every contributing superior source must be represented in `source_bindings`.

The requirement identity must be bound into:

```text
review material
decision request
human decision receipt
freeze verification state
```

## 7. Human Decision Receipt

The receipt is a decision record, not a permission system.

Minimum semantic fields:

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

It deliberately does not define trusted `permissions`, `roles`, `general_trust` or delegated capabilities.

Those facts must not become authoritative merely because the receipt contains them.

## 8. External authority evidence

```text
DECISION FACT != AUTHORITY TO MAKE THAT DECISION
```

External evidence must independently establish the facts demanded by the canonical authority requirement, such as:

```text
verified actor subject
verified issuer / trust owner
verified authority class / context
binding to decision event or request
freshness / validity required by the evidence profile
```

The freeze gate validates evidence against the canonical requirement.

It never asks the receipt what authority should have been required.

## 9. F-7 — Authority Substitution

Failure:

```text
correct authority requirement exists
        ↓
Human A / context A is required
        ↓
system accepts Human B / context B because "some human approved"
        ↓
freeze
```

Invariant:

```text
"SOME HUMAN APPROVED" != "THE REQUIRED AUTHORITY APPROVED"
AUTHORITY IDENTITY MUST BIND TO EXACT DECISION CONTEXT
```

## 10. F-8 — Authority Requirement Injection / Downgrade

Failure:

```text
SUPERIOR POLICY REQUIRES AUTHORITY A
        ↓
caller / model / task / formation profile injects weaker or different requirement B
        ↓
real actor valid for B approves
        ↓
system correctly verifies B
        ↓
freeze
```

The decision and evidence may be genuine.

The failure is that the system asked the wrong authorization question.

Distinction:

```text
F-7:
correct requirement
+ wrong authority principal/context accepted

F-8:
wrong or weakened requirement
+ correctly verified evidence for that wrong requirement
```

Invariants:

```text
AUTHORITY REQUIREMENT MUST COME FROM CANONICAL TRUSTED SOURCES
CALLER / MODEL MAY NOT SELECT OR DOWNGRADE REQUIRED AUTHORITY
LOWER TRUST MAY NOT OVERRIDE HIGHER TRUST
MISSING REQUIRED SOURCE OR REQUIREMENT = FAIL CLOSED
```

## 11. F-8 attacks against the trust hierarchy

Required attacks include:

```text
caller supplies required_authority
model labels task low risk and weakens requirement
task contract removes project requirement
formation profile invents its own authority class
formation profile chooses its own evidence issuer
missing project authority rule falls back to permissive default
stale project policy is used after canonical policy changes
one superior source is silently omitted during requirement composition
last-write-wins replaces conjunction
freeze gate authors its own weaker requirement
```

Every case must fail closed.

## 12. Authority requirement drift

Human approval must bind to the requirement that existed at review time.

```text
requirement A
    ↓
human reviews and accepts
    ↓
canonical policy changes to requirement B
    ↓
old approval reused
```

must fail.

Required behavior:

```text
canonical requirement changes
    -> new authority_requirement_sha256
    -> new review-material identity
    -> new decision-request identity
    -> previous human decision stale for freeze
    -> new review / decision required
```

## 13. Exact freeze rule

Only `ACCEPT` may be freeze-eligible.

Freeze gate must independently:

```text
1. verify identities of all canonical authority-requirement sources;
2. recompute / resolve the effective conjunctive requirement;
3. verify authority_requirement_sha256 against the review and receipt;
4. verify all required external evidence profiles/classes/contexts;
5. verify actor subject bindings;
6. verify exact decision-request identity;
7. verify exact review-material identity;
8. verify exact current draft == exact contract to be frozen;
9. verify exact formation profile / canonical task / Executor commit bindings.
```

It must not accept a precomputed requirement merely because the caller supplied a matching JSON object.

Any mismatch or missing superior source:

```text
AUTHORIZED_AND_FROZEN = FORBIDDEN
```

## 14. Freeze Gate is not a second IAM

Freeze Gate may know:

```text
required authority class identifiers
trusted evidence profile identifiers
canonical source identities/hashes
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

Those mutable ownership facts remain external.

The gate answers:

> Does independently verified evidence satisfy the canonically resolved requirement for this exact transition?

It does not answer:

> Who should be an admin in this organization?

## 15. Replay

No global one-time-use receipt ledger is introduced.

```text
same receipt
+ different request/contract/review/authority-requirement identity
= INVALID

same receipt
+ same immutable identities
+ same still-valid external authority evidence
= same authorization fact
```

Same-identity verification is idempotent, not a new delegation.

## 16. Required adversarial cases before implementation

At minimum:

1. caller-forged Human Decision Receipt;
2. fabricated authority evidence reference;
3. valid login but no required authority;
4. Human A receipt paired with Human B evidence;
5. correct actor under wrong organization/account context;
6. caller injects weaker requirement;
7. model proposes weaker requirement;
8. task contract deletes superior requirement;
9. formation profile invents authority requirement;
10. formation profile chooses caller-controlled evidence profile;
11. missing requirement falls back to permissive default;
12. one superior policy source omitted from conjunctive composition;
13. last-write-wins replaces a stricter/different superior requirement;
14. canonical requirement changes after human review;
15. wrong authority-requirement hash in receipt;
16. correct evidence for wrong authority class/context;
17. wrong contract/request/review identity;
18. stale approval after contract mutation;
19. old approval generalized to another task/action;
20. `REJECT` substituted as `ACCEPT`;
21. `MODIFY` executed without new formation/review;
22. missing/unverifiable external evidence;
23. decision adapter certifies its own evidence;
24. formation kernel acts as authority verifier;
25. freeze gate creates or weakens its own requirement;
26. receipt self-declared roles influence verifier.

Unauthorized result:

```text
FAIL CLOSED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 17. Current adversarial-review findings

```text
R-1 Authorization Receipt was too strong
    -> Human Decision Receipt

R-2 decision adapter role was too broad
    -> decision capture separated from authority evidence

R-3 receipt self-described its bounded authority
    -> boundedness moved to verifier exact-identity semantics

R-4 authority substitution was implicit
    -> F-7 explicit

R-5 authority context ownership was ambiguous
    -> requirement separated from external authority ownership

R-6 caller-selected weak requirement could still pass honest verification
    -> F-8 explicit

R-7 authority requirement could drift after review
    -> requirement hash bound into review / request / receipt / freeze

R-8 formation profile appeared able to own authority requirement
    -> rejected because current Executor trust hierarchy places executor_policy and project_contract above task/generated layers

R-9 simple "last requirement wins" composition could erase superior constraints
    -> effective authority requirement is conjunctive; lower layers may add but not remove
```

F-7 and F-8 must be reflected in PR #51 before #51 is ever merged.

## 18. Current conclusion of Authority Context Ownership Review

The design now has a provisional ownership answer:

```text
EXECUTOR_POLICY
  owns trust hierarchy / system minimums

PROJECT_CONTRACT or equivalent superior project governance
  owns project-specific authority requirements

TASK / FORMATION LAYERS
  consume, reference or add constraints
  cannot weaken superior requirements

EXTERNAL AUTHORITY SYSTEM
  owns mutable truth about who currently possesses authority

FREEZE GATE
  independently resolves requirements and verifies evidence
  owns neither IAM membership nor requirement policy
```

This avoids both bad extremes:

```text
caller declares authority context
```

and:

```text
Freeze Gate becomes a full IAM database
```

## 19. Next unresolved design question

Implementation remains blocked.

The next root-of-trust question is narrower:

> **How does the Freeze Gate verify the canonical identity/version of project-level authority policy without trusting mutable candidate/workspace content?**

The answer must reuse an existing superior canonical/evidence boundary where possible rather than invent another authority system.
