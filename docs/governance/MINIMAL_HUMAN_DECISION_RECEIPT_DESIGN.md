---
document: "Minimal Human Decision Receipt Design"
version: "0.7"
status: "EXTERNAL AUTHORITY EVIDENCE TRUST REVIEW / IMPLEMENTATION BLOCKED"
date: "2026-08-09"
scope: "human decision record, canonical authority requirements, canonical evidence trust, intent ownership and exact freeze verification"
repository: "litrgratis-pixel/Executor"
---

# Minimal Human Decision Receipt Design v0.7

## 1. Governing invariants

```text
HUMAN DECISION RECEIPT != VERIFIED AUTHORITY EVIDENCE
AUTHENTICATION != AUTHORIZATION
AUTHORIZATION != DELEGATION
AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP
AUTHORITY REQUIREMENT != AUTHORITY EVIDENCE SOURCE
VALID POLICY CONTENT != CANONICAL POLICY AUTHORITY
EVIDENCE REF != TRUST SELECTOR
LOWER TRUST MAY NOT WEAKEN HIGHER TRUST
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

The purpose of this design is not to build an IAM system.

It is to define why one exact human decision may allow one exact draft contract to become frozen while every ambiguous or substituted path fails closed.

## 2. End-to-end boundary

```text
USER REQUEST
    ↓
FORMATION KERNEL
    exact draft + review + decision request
    ↓
CANONICAL AUTHORITY REQUIREMENT RESOLUTION
    ↓
CANONICAL EVIDENCE TRUST RESOLUTION
    ↓
HUMAN DECISION ADAPTER
    presents exact material and records an observed action
    DOES NOT prove authority or choose issuer/verifier
    ↓
HUMAN DECISION RECEIPT
    local bound record; IS NOT PROOF
    ↓
EXTERNAL EVIDENCE
    proves decision event + required authority fact
    ↓
FREEZE GATE
    re-verifies canonical sources, trust profile, claims and exact identities
    ↓
AUTHORIZED_AND_FROZEN
```

No component may silently combine contract interpretation, authority-policy ownership, trust-provider selection, human-action capture, evidence issuance, evidence verification and freeze.

## 3. Existing Executor trust hierarchy remains the policy root

`EXECUTOR_POLICY.yaml` already defines:

```text
executor_policy
> project_contract
> task_contract
> authoritative_source
> untrusted_repository_data
> generated_data
```

The human-authority design reuses this hierarchy.

It does not introduce `ExecutorIAM`, `AuthorityPolicyStore`, an authority database or a second policy root.

For current GP001, the verified Executor repository identity, exact Executor commit, project bundle and tracked `EXECUTOR_POLICY.yaml` remain the canonical source boundary.

## 4. Requirement, ownership and evidence source are separate

```text
AUTHORITY REQUIREMENT
  says WHAT must be proved

AUTHORITY OWNERSHIP
  external system knows WHO currently possesses that authority

AUTHORITY EVIDENCE SOURCE
  says WHICH independently verifiable source may prove the required facts
```

Core invariant:

```text
AUTHORITY REQUIREMENT
!= AUTHORITY OWNERSHIP
!= AUTHORITY EVIDENCE SOURCE
```

Executor may know requirements and proof rules without owning mutable user/organization role truth.

## 5. Requirement ownership by trust layer

```text
EXECUTOR_POLICY
  system-wide non-bypassable minima
        ↓
PROJECT_CONTRACT / superior project governance
  project/domain requirements
        ↓
TASK CONTRACT
  may add narrower constraints
  may not remove superior constraints
        ↓
FORMATION PROFILE
  process configuration/reference only
  NOT an authority-policy owner
```

Effective requirements compose conjunctively:

```text
SYSTEM REQUIREMENTS
AND PROJECT REQUIREMENTS
AND VALID ADDITIONAL TASK REQUIREMENTS
```

No `last-write-wins` authority semantics are allowed.

## 6. Canonical authority requirement identity

A resolved authority requirement is immutable verification material, not an IAM database.

Minimum semantics:

```text
schema_version
authority_requirement_id
required_authority_classes[]
required_context_bindings{}
evidence_trust_profile_refs[]
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

This hash is part of review/decision identity.

## 7. Canonical Evidence Trust Profile

An Evidence Trust Profile answers:

> Which external source and verification rules are allowed to prove the required authority facts?

It is policy material, not mutable membership data.

Conceptual minimum semantics:

```text
trust_profile_id
allowed_issuer_identity / issuer namespace
verification_profile_id
required_claim_classes[]
required_context_bindings[]
freshness policy
revocation/status policy when supported
source_bindings[]
executor_commit
```

Canonical serialization yields:

```text
evidence_trust_profile_sha256
```

The profile must come from canonical superior sources under the existing Executor trust hierarchy.

Caller, model, formation profile or receipt may not create/select a new trust profile at runtime.

For the first implementation slice, one exact canonical external trust profile is preferred. No provider shopping or fallback.

## 8. Trust snapshot is not caller-constructable

The design follows the existing `ExecutionPolicySnapshot` pattern:

```text
CALLER INPUT != VERIFIED TRUST SNAPSHOT
```

A future trust snapshot must exist only after verifying canonical repository/project/policy source identity.

Public APIs must not accept caller-controlled trust-selection parameters such as:

```text
issuer=
verifier=
trust_profile=
verification_endpoint=
keyset_url=
allowed_issuers=
```

## 9. `authority_evidence_ref` is only a locator

The receipt may contain evidence references, but a reference may not decide:

```text
which issuer is trusted
which verifier runs
which network origin is trusted
which key set/trust root is used
which authority class is required
```

Core invariant:

```text
EVIDENCE REF != TRUST SELECTOR
```

If evidence contains an issuer identifier, it is checked against the canonical trust profile. It is not used to discover a new trusted provider.

An arbitrary caller-provided URL is not a trust boundary.

## 10. Human Decision Receipt

The receipt is a local bound record, not proof and not a permission system.

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
evidence_trust_profile_sha256
formation_profile_sha256
canonical_task_sha256
executor_commit
decision_event_id
observed_at
freshness_id
```

Schema validity never creates trust.

## 11. External evidence proves two claim classes

The decision adapter is not the final root of truth even for the statement that a human action occurred.

External evidence must collectively establish:

### A. Decision Event Evidence

```text
verified actor subject
exact decision value
exact decision-event identity
exact decision_request_sha256 or equivalent bound identity
freshness/validity required by the trust profile
```

### B. Authority Entitlement / Ownership Evidence

```text
same verified actor subject
required authority class/ownership relation
required authority context
validity/freshness status
canonical issuer/trust-profile identity
```

One artifact may prove both. Multiple artifacts may jointly prove them.

The Freeze Gate verifies claims, not file count.

## 12. Critical product distinction: intent authority vs action authority

`REQUEST_TO_CONTRACT_001` governs interpretation of a human request.

Its immediate authority question is:

> Did the human who owns this request/goal authorize this exact interpretation as the task contract?

That is not the same question as:

> Does this actor have operational permission to mutate repository R, deploy production or use credential C?

Therefore:

```text
INTENT AUTHORITY
    !=
RESOURCE / ACTION AUTHORITY
```

For the first GP001 formation slice, the minimal authority class SHOULD be the verified **request/goal owner**, not a new generalized organization role model.

The contract-formation approval may authorize only:

```text
this exact interpretation
of this exact request
into this exact frozen task contract
```

It does NOT by itself authorize:

```text
WRITE_REPOSITORY
MERGE
DEPLOY
NETWORK
SECRET USE
OTHER CONSEQUENT ACTIONS
```

Those remain downstream policy/AAP/action-authority questions.

## 13. Minimal first-slice authority requirement

The first controlled `REQUEST_TO_CONTRACT_001` design therefore requires a future canonical superior source to establish an authority class equivalent to:

```text
REQUEST_INTENT_OWNER
```

Meaning:

```text
the actor authorized to approve formation
must be the same externally verified principal
that originated/owns the governed user request
```

The name above is a design label, not yet a frozen schema value.

The requirement must be sourced from canonical superior policy/project governance before implementation. Formation profile alone is insufficient.

Current `main` has `human_authorization_required: true` in the formation profile but does not yet define this exact canonical authority class in a superior source.

Therefore implementation remains blocked until the superior model/policy defines the formation authority requirement explicitly.

## 14. Minimal first-slice Evidence Trust Profile claims

Without choosing OAuth, OIDC, passkeys, GitHub or another provider, the first profile must be able to prove at least:

```text
1. verified_request_originator_subject
2. verified_decision_actor_subject
3. originator_subject == decision_actor_subject
4. exact decision == ACCEPT
5. exact decision_request_sha256
6. exact decision_event identity
7. evidence comes from the canonical trust profile / issuer
8. evidence is fresh/valid under canonical rules at freeze
```

Because `decision_request_sha256` binds the reviewed draft, review material, authority requirement and trust-profile identity, this is enough for the first formation slice without importing a generic enterprise role graph.

If a future project requires a different authority owner than the request originator, that must be an explicit superior governance requirement and a separate product slice.

## 15. Request-origin identity is also externally rooted

The field:

```text
request_originator = "USER"
```

is not proof.

The original request itself must carry or resolve to externally verified originator identity evidence under the same canonical trust boundary.

Formation may preserve this identity binding.

Formation may not manufacture or replace it.

Therefore the first slice ultimately compares two externally rooted facts:

```text
VERIFIED REQUEST ORIGINATOR
        ==
VERIFIED DECISION ACTOR
```

plus the exact decision-request binding.

## 16. Evidence context binding

A true actor and a true role are insufficient if context differs.

Evidence must satisfy all canonical context bindings applicable to the authority requirement, such as:

```text
request owner identity
project/repository context when required
organization/tenant when required by a future slice
decision request identity
decision event identity
validity interval
```

Cross-context evidence is invalid.

## 17. Freshness and revocation semantics

Receipt timestamps are not proof of freshness.

The canonical trust profile defines what `valid now` means.

For the first slice, Freeze Gate must fail closed unless it can establish:

```text
decision event occurred in the accepted validity window
AND
required evidence remains valid under the canonical trust profile at freeze
```

If required status is `UNKNOWN`, unavailable or stale, freeze is blocked.

No silent cached or weaker fallback is allowed.

## 18. Failure modes retained

### F-4 — Self-Declared Decision Authority

Caller-created `human approved` claims are not evidence.

### F-5 — Approval Drift

Approval of draft A cannot authorize later draft B.

### F-6 — Authorization Generalization / Delegation Drift

Approval of one contract cannot become standing trust.

### F-7 — Authority Substitution

Wrong actor/account/authority context cannot substitute for the required authority.

### F-8 — Authority Requirement Injection / Downgrade

Lower-trust input cannot replace the true required authority with a weaker one.

### F-9 — Authority Policy Source Substitution

Valid-looking policy content from the wrong repository/commit/path/source role is not canonical authority.

### F-10 — Evidence Self-Issuance

Executor/Formation/Decision Adapter/Freeze Gate cannot be the sole issuer/root of the human-authority evidence it later accepts.

### F-11 — Issuer Substitution / Provider Shopping

Caller/adapter cannot choose another provider or try providers until one returns YES.

### F-12 — Evidence Scope Drift

Valid evidence for another request/project/org/tenant/time is invalid here.

### F-13 — Verifier / Trust Profile Substitution

Evidence cannot choose its own verifier, endpoint, trust root, discovery source or permissive verification mode.

### F-14 — Evidence Freshness / Revocation Drift

Evidence that was once valid is not automatically valid for the current freeze.

## 19. F-15 — Authority Dimension Conflation

New failure class from this review.

Failure A:

```text
request owner approves contract meaning
        ↓
system treats that approval as permission to WRITE / MERGE / DEPLOY
```

Failure B:

```text
resource admin has permission to deploy/write
        ↓
system treats resource authority as ownership of the user's intent
        ↓
admin silently changes/approves what the request means
```

Both are wrong.

Invariant:

```text
CONTRACT-FORMATION AUTHORITY != CONSEQUENT ACTION AUTHORITY
RESOURCE AUTHORITY != OWNERSHIP OF USER INTENT
```

Each transition must be authorized by the authority dimension that owns that transition.

## 20. Trust and requirement drift after review

Any change to:

```text
canonical authority requirement sources
authority_requirement_sha256
canonical evidence trust profile
evidence_trust_profile_sha256
request-origin identity binding
review material
draft contract
Executor formation identity
```

invalidates the previous decision for freeze.

Correct behavior:

```text
change
→ new canonical identity
→ new review/decision request
→ previous decision stale
→ new human review required
```

## 21. Exact Freeze Gate semantics

Only `ACCEPT` may be freeze-eligible.

Freeze Gate must independently:

```text
1. re-verify exact Executor/project canonical source identities;
2. resolve and conjunctively compose authority requirements;
3. recompute authority_requirement_sha256;
4. resolve canonical Evidence Trust Profile;
5. recompute evidence_trust_profile_sha256;
6. verify exact request-origin identity evidence;
7. verify receipt hashes against current review/request/contract state;
8. resolve evidence refs only inside canonical trust rules;
9. verify external issuer using canonical verification semantics;
10. verify Decision Event Evidence;
11. verify Authority Entitlement/Ownership Evidence;
12. require verified request originator == verified decision actor for first slice;
13. verify exact decision/context bindings;
14. verify freshness/status;
15. verify current draft hash == contract hash to freeze.
```

Any missing, unknown, stale or mismatched required fact:

```text
AUTHORIZED_AND_FROZEN = FORBIDDEN
```

## 22. Freeze Gate remains verifier, not IAM

Freeze Gate may know:

```text
canonical source identities
required authority-class identifiers
canonical trust-profile identity
verification rules
expected exact context bindings
```

It must not own:

```text
users
organization membership
role assignments
standing delegation
provider fallback invented at runtime
```

It also may not mint the sole evidence it accepts as human-authority proof.

## 23. Replay semantics

No global one-time human-decision receipt ledger is introduced.

```text
same receipt + different requirement/trust/request/contract/review/origin context = INVALID
same receipt + same immutable identities + still-valid evidence = same authorization fact
```

Exactly-once consequential action remains a separate action-consumption property.

## 24. Required adversarial cases before implementation

The future boundary must reject at least:

1. caller-forged Human Decision Receipt;
2. fabricated evidence reference;
3. caller-forged request-originator identity;
4. decision actor differs from verified request originator in first slice;
5. valid login without exact decision binding;
6. Human A receipt paired with Human B evidence;
7. caller/model injects weaker authority requirement;
8. formation profile invents required authority;
9. task removes superior requirement;
10. missing superior authority source defaults permissively;
11. wrong policy/project repository or commit;
12. dirty/untracked/copied authority policy;
13. caller-selected alternative trust profile;
14. receipt-selected issuer/provider;
15. arbitrary evidence URL selects origin;
16. Executor/adapter self-issues sole evidence;
17. correct issuer string with attacker-selected permissive verifier;
18. evidence selects its own discovery endpoint/trust root;
19. valid evidence for wrong decision request/context;
20. expired/revoked/stale authority evidence;
21. required status unavailable/unknown;
22. provider unavailable and runtime falls back to weaker provider;
23. trust profile changes after review;
24. wrong requirement/trust-profile hash in receipt;
25. `REJECT` substituted as `ACCEPT`;
26. `MODIFY` executed without new review;
27. old approval generalized as standing trust;
28. decision adapter claims human action without external event proof;
29. intent-owner approval reused as `WRITE_REPOSITORY` authority;
30. resource/admin authority reused as permission to redefine user intent;
31. Freeze Gate authors/selects weaker requirement, provider or verifier.

Expected:

```text
FAIL CLOSED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 25. Current design findings

```text
R-1 Authorization Receipt -> Human Decision Receipt
R-2 decision capture separated from authority evidence
R-3 boundedness moved from receipt claims to verifier semantics
R-4 F-7 Authority Substitution explicit
R-5 requirement separated from external authority ownership
R-6 F-8 Authority Requirement Injection/Downgrade explicit
R-7 requirement drift bound into decision identity
R-8 formation profile rejected as authority owner
R-9 requirement composition made conjunctive
R-10 F-9 Authority Policy Source Substitution explicit
R-11 existing project/policy verification reused; no second policy root
R-12 authority requirement separated from evidence source
R-13 evidence ref reduced to locator only
R-14 external evidence must prove event + entitlement/ownership
R-15 F-10 Self-Issuance explicit
R-16 F-11 Issuer Substitution / Provider Shopping explicit
R-17 F-12 Evidence Scope Drift explicit
R-18 F-13 Verifier / Trust Profile Substitution explicit
R-19 F-14 Freshness / Revocation Drift explicit
R-20 trust-profile identity bound through review/decision/freeze
R-21 contract-formation authority separated from resource/action authority
R-22 minimal first-slice authority reduced to verified request/goal owner
R-23 original request identity itself must be externally rooted
R-24 F-15 Authority Dimension Conflation explicit
```

F-7 through F-15 must be reconciled into the superior human-authority model before that model is merged.

## 26. Current design gap discovered on `main`

Current formation profile states:

```text
human_authorization_required: true
```

but no superior canonical source currently defines the exact formation authority class/trust-profile identity required for `REQUEST_TO_CONTRACT_001`.

Because formation profile is not an authority owner, implementation MUST NOT infer a default such as `USER` or accept caller-selected authority.

This is a deliberate fail-closed design blocker, not an invitation to hard-code an identity technology.

## 27. External Authority Evidence Trust Review — current result

The evidence trust problem is substantially resolved at the design level:

```text
SUPERIOR POLICY / PROJECT GOVERNANCE
  owns requirement + accepted evidence trust profile

EXTERNAL TRUST SOURCE
  roots request-origin + decision-event + authority facts

HUMAN DECISION ADAPTER
  presents material / records local event
  owns no trust-provider selection

HUMAN DECISION RECEIPT
  records exact bindings and refs
  is not proof

FREEZE GATE
  verifies canonical trust snapshot + external claims
  owns neither IAM nor policy
```

For the first GP001 formation slice, the narrowest defensible human-authority requirement is:

```text
VERIFIED REQUEST / GOAL OWNER
must explicitly ACCEPT
this exact decision request
```

not a generic organization IAM role.

## 28. Gate

```text
AUTHORITY CONTEXT OWNERSHIP: SUBSTANTIALLY RESOLVED
EXTERNAL AUTHORITY EVIDENCE TRUST: SUBSTANTIALLY RESOLVED
FIRST-SLICE AUTHORITY DIMENSION: IDENTIFIED
IMPLEMENTATION: BLOCKED
MERGE: NO
```

One final design action remains before PR #52 can be considered for acceptance:

> Reconcile the superior model (#51) so it explicitly distinguishes intent authority from action authority and defines that the first REQUEST_TO_CONTRACT_001 slice requires externally verified request/goal-owner approval, while leaving provider technology unresolved.

Only after that model alignment should PR #52 be reconsidered for ACCEPT. No boundary implementation should begin before then.
