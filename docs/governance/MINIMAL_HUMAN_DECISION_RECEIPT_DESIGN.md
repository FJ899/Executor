---
document: "Minimal Human Decision Receipt Design"
version: "0.3"
status: "AUTHORITY CONTEXT OWNERSHIP REVIEW / IMPLEMENTATION BLOCKED"
date: "2026-08-09"
scope: "human decision record, canonical authority requirement, external authority evidence, exact freeze verification"
repository: "litrgratis-pixel/Executor"
---

# Minimal Human Decision Receipt Design v0.3

```text
HUMAN DECISION RECEIPT != VERIFIED AUTHORITY EVIDENCE
VERIFIED AUTHORITY EVIDENCE != AUTHORIZED CONTRACT
AUTHENTICATION != AUTHORIZATION
AUTHORIZATION != DELEGATION
AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP
```

## 1. Boundary

```text
FORMATION KERNEL
  creates exact draft + review + decision request
        ↓
CANONICAL AUTHORITY REQUIREMENT
  states what authority proof is required
  DOES NOT name who currently owns that authority
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
  verifies requirement source + evidence + current exact identities
        ↓
AUTHORIZED_AND_FROZEN
```

No component may silently combine:

- contract interpretation;
- authority-requirement selection;
- human decision capture;
- authority ownership;
- evidence verification;
- contract mutation;
- freeze.

## 2. Human Decision Receipt

The receipt is a record, not a permission system.

Minimum semantic fields:

```text
schema_version
receipt_id
decision_request_id
decision_request_sha256
actor_subject
authority_evidence_ref
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

It deliberately does not define:

```text
permissions
roles
allowed_actions
general_trust
delegated_capabilities
```

It records the decision fact and points to external authority evidence. It does not itself explain why the actor had authority.

## 3. Authority requirement versus authority ownership

Core invariant:

> **AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP.**

Executor may know:

```text
WHAT authority class is required
WHICH external trust profile / evidence verifier is acceptable
WHICH exact decision request the requirement applies to
```

without owning:

```text
WHO currently holds that authority
WHICH users belong to which organization
WHICH roles are assigned to which people
WHICH permissions exist in the external organization
```

Incorrect architecture:

```text
FREEZE GATE
  + users
  + organizations
  + RBAC
  + permissions
  + role assignments
```

That would make the freeze gate a second IAM system.

Correct architecture:

```text
CANONICAL AUTHORITY POLICY / FORMATION PROFILE
        ↓
AUTHORITY REQUIREMENT
        ↓
EXTERNAL AUTHORITY SYSTEM
        ↓
AUTHORITY EVIDENCE
        ↓
FREEZE GATE
```

The external authority system owns the changing fact of who has authority.

Executor owns only the rule describing what proof must be presented for the current governed transition.

## 4. Authority requirement source

The required authority context must never originate from caller input, model convenience, receipt fields, or freeze-gate defaults.

Rejected:

```text
required_authority_context = caller_input
```

Rejected:

```text
if missing_required_authority:
    default_to_low_risk
```

Rejected:

```text
model says this looks low risk
    -> require LOW_RISK_APPROVER
```

The minimal design requires the authority requirement to be derived from a canonical, independently identity-bound source already trusted for the formation decision.

Conceptually:

```text
VERIFIED EXECUTOR COMMIT
        +
CANONICAL FORMATION PROFILE / GOVERNING POLICY
        ↓
AUTHORITY REQUIREMENT
```

The exact long-term owner may later be a project policy, organization policy, or another superior governance artifact. The important property is that the formation caller cannot choose or weaken it for the current request.

## 5. Minimal authority requirement identity

The requirement is not an IAM database. It is a small immutable verification requirement.

Minimum semantics:

```text
schema_version
authority_requirement_id
authority_class
trusted_evidence_profile_id
required_authority_context_key
source_artifact_identity
source_artifact_sha256
formation_profile_sha256
canonical_task_sha256
executor_commit
```

Canonical serialization produces:

```text
authority_requirement_sha256
```

The decision request and review material must bind to this exact requirement identity.

The requirement may say, for example:

```text
authority_class: PRODUCTION_DEPLOYMENT_APPROVER
trusted_evidence_profile_id: COMPANY_IAM_PROD_APPROVAL_V1
required_authority_context_key: service/prod
```

It must not say:

```text
Jan Kowalski is currently an approver
```

That mutable ownership fact belongs to the external authority system.

## 6. External authority evidence

```text
DECISION FACT != AUTHORITY TO MAKE THAT DECISION
```

The evidence referenced by `authority_evidence_ref` must be independently verifiable and establish at least:

```text
verified actor subject
verified evidence issuer / trust owner
verified authority class / context
binding to the relevant decision event or decision request
freshness / validity required by the chosen mechanism
```

The freeze gate verifies this evidence against the canonical authority requirement.

It does not trust an authority class copied from the receipt.

## 7. F-7 — Authority Substitution

```text
HUMAN A approves contract C
        ↓
system verifies only "some authenticated human approved"
        ↓
Human B / wrong account / wrong authority context
is treated as equivalent
        ↓
freeze
```

```text
F-4: no verified human decision exists
F-5: approval reused after contract identity changes
F-6: bounded approval generalized to another contract/action
F-7: wrong actor or authority context substituted as equivalent
```

Invariant:

```text
"SOME HUMAN APPROVED" != "THE REQUIRED AUTHORITY APPROVED"
AUTHORITY IDENTITY MUST BIND TO EXACT DECISION CONTEXT
```

## 8. F-8 — Authority Requirement Injection / Downgrade

Failure mechanism:

```text
REAL ACTION REQUIRES HIGHER AUTHORITY
        ↓
caller / model / mutable local state supplies:
required_authority = LOW_RISK_APPROVER
        ↓
system correctly verifies a real LOW_RISK_APPROVER
        ↓
contract freezes
```

The human decision and authority evidence may both be genuine.

The failure is earlier:

> The system required the wrong authority.

This differs from F-7:

```text
F-7:
correct authority requirement
+ wrong principal/context accepted

F-8:
wrong / weakened authority requirement
+ correctly verified weaker principal
```

Invariants:

```text
AUTHORITY REQUIREMENT MUST COME FROM A CANONICAL TRUSTED SOURCE
CALLER MAY NOT SELECT OR DOWNGRADE REQUIRED AUTHORITY
MISSING AUTHORITY REQUIREMENT MUST FAIL CLOSED
```

Any change to the authority requirement creates a new identity and invalidates the old decision request / review cycle.

## 9. Authority requirement drift

The requirement is part of the governed state.

Therefore:

```text
requirement A
  -> human reviews / decides under A
  -> policy changes requirement to B
  -> old receipt reused
```

must fail.

Required behavior:

```text
any canonical authority-requirement change
        -> new authority_requirement_sha256
        -> new decision_request_sha256
        -> previous human decision becomes stale for freeze
        -> new review / authorization required
```

This prevents policy or requirement drift from bypassing exact decision binding.

## 10. Exact freeze rule

Only `ACCEPT` may be freeze-eligible.

Future freeze requires:

```text
receipt.decision == ACCEPT

canonical authority requirement independently resolved
canonical authority requirement source identity verified

receipt.authority_requirement_sha256
== current authority_requirement_sha256

external authority evidence independently valid
verified evidence profile
== requirement.trusted_evidence_profile_id
verified authority class/context
== requirement.authority_class/context
verified actor subject
== receipt.actor_subject

receipt.decision_request_sha256
== current decision_request_sha256

receipt.reviewed_contract_sha256
== current draft hash
== frozen contract hash

receipt.review_material_sha256
== current review-material hash

receipt.formation_profile_sha256
== current formation-profile hash

receipt.canonical_task_sha256
== current canonical-task hash

receipt.executor_commit
== current exact Executor formation commit
```

Boundedness comes from exact verifier acceptance against one canonical requirement + one decision request + one contract identity.

Any mismatch:

```text
AUTHORIZED_AND_FROZEN = FORBIDDEN
```

## 11. Freeze Gate responsibility

The freeze gate is a verifier, not an IAM owner and not an authority-requirement author.

It may:

```text
resolve the canonical authority requirement by trusted identity
verify its source hash / binding
verify external evidence using the required evidence profile
compare actor / context / decision / contract identities
freeze only the exact approved contract
```

It may not:

```text
choose a weaker authority requirement
accept caller-selected authority context
invent role membership
maintain organization membership as authority truth
reinterpret the user request
modify the contract
convert MODIFY / REJECT into ACCEPT
```

## 12. Decision semantics

`ACCEPT` proceeds only to exact authority + identity verification.

`MODIFY` requires a new draft, hash, critique, review material, authority requirement binding, decision request, and human decision.

`REJECT` never authorizes.

## 13. Replay

No global one-time-use receipt ledger is introduced.

```text
same receipt + different request/contract/review/authority-requirement identity = INVALID
same receipt + same immutable identities + same still-valid authority evidence = same authorization fact
```

Same-identity revalidation is idempotent verification, not new or broader authority.

## 14. Adversarial cases required before implementation

At minimum test:

1. caller-forged receipt;
2. fabricated authority evidence reference;
3. authenticated actor without authority for this context;
4. Human A receipt paired with Human B evidence;
5. correct subject under wrong account/organization context;
6. caller injects a weaker `required_authority`;
7. model proposes a weaker authority requirement than canonical policy;
8. missing authority requirement falls back to a permissive default;
9. authority requirement points to caller-selected evidence issuer/profile;
10. canonical requirement changes after human review;
11. wrong authority-requirement hash in receipt;
12. correct authority evidence for the wrong requirement class;
13. wrong contract/request/review hashes;
14. stale approval after contract A -> B;
15. receipt reused across another contract/request;
16. old approval treated as standing trust;
17. `REJECT` -> `ACCEPT` substitution;
18. `MODIFY` used to execute without re-review;
19. authority issuer/context mismatch;
20. missing/unverifiable authority evidence;
21. decision adapter certifies its own evidence;
22. formation kernel acts as evidence verifier;
23. freeze gate authors or downgrades its own authority requirement;
24. review material changes after human action;
25. receipt self-declared permissions influence verifier;
26. valid login/session without exact decision binding.

Unauthorized result:

```text
FAIL CLOSED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 15. Current adversarial-review findings

```text
R-1 Human Authorization Receipt was too strong
    -> Human Decision Receipt

R-2 adapter role was too broad
    -> split decision capture from authority evidence

R-3 receipt self-described bounded authority
    -> boundedness moved to freeze-gate exact identity semantics

R-4 authority substitution was implicit
    -> F-7 made explicit

R-5 authority context ownership was ambiguous
    -> authority requirement separated from authority ownership

R-6 caller-selected / weak requirement could make valid weak approval look sufficient
    -> F-8 Authority Requirement Injection / Downgrade

R-7 authority requirement itself could drift after review
    -> requirement identity is bound into review + decision request + freeze
```

F-7 and F-8 should also be reflected in PR #51 before #51 is ever merged.

## 16. Next design question

Implementation remains blocked.

The current design now answers where the requirement comes from conceptually, but one root-of-trust question remains:

> **What exactly makes an authority-requirement source canonical and trusted without allowing the formation code or mutable project workspace to rewrite that source?**

Until that ownership is explicit, the system could merely move F-8 one layer upward.
