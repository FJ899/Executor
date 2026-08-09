---
document: "Minimal Verified Human Authority Implementation Contract"
version: "0.2"
status: "ADVERSARIAL DRAFT / NON-EXECUTABLE IMPLEMENTATION CONTRACT"
date: "2026-08-09"
scope: "first REQUEST_TO_CONTRACT_001 verified-human-authority boundary between verified formation state and future freeze gate"
repository: "litrgratis-pixel/Executor"
depends_on:
  - "docs/governance/VERIFIED_HUMAN_AUTHORITY_MODEL.md"
  - "docs/governance/MINIMAL_HUMAN_DECISION_RECEIPT_DESIGN.md"
---

# Minimal Verified Human Authority Implementation Contract v0.2

## 1. Purpose

This document defines the smallest implementation boundary that may later establish verified human authority for the first `REQUEST_TO_CONTRACT_001` slice.

It is **not implementation**. It does not select a UI, identity provider, OAuth/OIDC flow, signature scheme, passkey, GitHub approval mechanism, IAM database, organization model or receipt ledger.

The boundary exists only to answer:

> Did the same externally verified principal who originated/owns this exact user request explicitly ACCEPT this exact decision request for this exact reviewed draft, under canonical trust rules, with evidence still valid for freeze?

Core rule:

```text
VERIFIED REQUEST ORIGINATOR
        ==
VERIFIED DECISION ACTOR
+
EXACT DECISION / REQUEST / REVIEW / DRAFT BINDING
+
CANONICAL TRUST SOURCE
+
VALID EXTERNAL EVIDENCE
        =
VERIFIED HUMAN AUTHORITY FOR CONTRACT FORMATION
```

This is **intent authority only**.

```text
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

A successful result does not itself authorize repository writes, merge, deploy, network, secret use or any other consequential action.

## 2. Required trust separations

The implementation must preserve all of these separations:

```text
REQUEST != CONTRACT
DRAFT CONTRACT != AUTHORIZED CONTRACT
HUMAN DECISION RECEIPT != VERIFIED AUTHORITY EVIDENCE
AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP
AUTHORITY REQUIREMENT != AUTHORITY EVIDENCE SOURCE
EVIDENCE REF != TRUST SELECTOR
FORMATION REQUEST STRUCTURE != VERIFIED FORMATION STATE
VERIFICATION RESULT STRUCTURE != VERIFIED AUTHORITY FACT
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

A syntactically valid object never becomes trusted merely because it names a trusted state.

## 3. Existing formation boundary is upstream, but its export is not proof

`RequestToContract001` currently stops at:

```text
AWAITING_VERIFIED_HUMAN_AUTHORIZATION
```

and exports:

```text
schema_version: executor-human-formation-authorization-request/1.0
request_id
executor_repository
executor_commit
formation_profile
formation_profile_sha256
canonical_task_sha256
draft_sha256
allowed_decisions
decision_surface
required_authority
status
```

The future boundary must reuse this formation path rather than inventing a parallel request-to-contract representation.

However:

```text
AUTHORIZATION REQUEST JSON
        !=
VERIFIED CURRENT FORMATION STATE
```

The current export carries `draft_sha256` but does not contain the complete canonical formation-draft snapshot needed for an independent verifier to recompute every draft field from that JSON alone.

Therefore a future compliant implementation must do one of two things:

1. consume a **non-caller-constructable Verified Formation Snapshot** created only from the verified `RequestToContract001` state; or
2. receive enough canonical formation material to independently reconstruct and verify the exact draft, critique, review material and authorization request from the pinned Executor formation inputs.

The verifier must never accept caller-supplied `status`, `draft_sha256`, `profile_sha256` or similar labels as sufficient proof of upstream state.

## 4. First-slice authority dimension

The only authority class in scope is conceptually:

```text
REQUEST_INTENT_OWNER
```

Meaning:

```text
actor allowed to ACCEPT the formed contract
==
externally verified principal that originated/owns the governed request
```

No organization administrator, repository owner, production approver, security approver, delegated approver or quorum semantics are introduced.

Later authority dimensions require separate canonical requirements.

## 5. Subject identity is a bound identity, not a bare string

For the first slice, equality means equality inside one canonical subject namespace/trust profile.

Required comparison is conceptually:

```text
request_originator_subject_binding
        ==
decision_actor_subject_binding
```

where a subject binding includes at least:

```text
canonical trust profile / issuer namespace
stable external subject identifier
```

Therefore:

```text
subject_id = "123"
from issuer A
        !=
subject_id = "123"
from issuer B
```

The first slice does not implement cross-provider account linking, federation mapping or identity correlation.

## 6. Required input classes

The boundary may return a positive result only when all required input classes are independently verified.

### A. Verified Formation State

Must establish at least:

```text
request_id
verbatim user request / canonical user-request digest
executor repository + exact executor commit
formation profile id + sha256
canonical task sha256
complete current formation draft identity
critique state
current status == AWAITING_VERIFIED_HUMAN_AUTHORIZATION
exact review material / decision surface
exact authorization request identity
```

This cannot originate from arbitrary caller object construction.

### B. Canonical Authority Requirement Snapshot

Must resolve from verified superior governance, never from caller/model/receipt input.

Minimum semantics:

```text
authority_dimension: REQUEST_INTENT
authority_class: REQUEST_INTENT_OWNER
required_subject_relation: REQUEST_ORIGINATOR_EQUALS_DECISION_ACTOR
source_bindings[]
executor_commit
authority_requirement_sha256
```

The snapshot must follow Executor's existing non-caller-constructable verified-snapshot principle.

### C. Canonical Evidence Trust Snapshot

Must resolve from canonical superior policy/project sources.

Minimum semantics:

```text
trust_profile_id
allowed external issuer / subject namespace / trust-root identity
verification_profile_id
required claim classes
required context bindings
freshness / validity rules
source_bindings[]
executor_commit
evidence_trust_profile_sha256
```

Public APIs may not accept runtime trust-selection parameters such as:

```text
issuer=
verifier=
trust_profile=
verification_endpoint=
keyset_url=
allowed_issuers=
```

that could replace the canonical trust decision.

### D. Request-Origin Evidence

External evidence must establish at least:

```text
verified request-originator subject binding
exact request event / request identity binding
binding to the verbatim request represented by formation
canonical trusted source identity
required validity / freshness
```

A process-local field such as `originator = USER` is not evidence.

### E. Decision-Event Evidence

External evidence must establish at least:

```text
verified decision-actor subject binding
decision == ACCEPT
exact decision-event identity
exact decision-request identity
required validity / freshness
canonical trusted source identity
```

A local `user_clicked_button = true` event is not sufficient proof by itself.

The origin and decision claims may be carried by one externally verifiable artifact or multiple artifacts. The contract constrains claims, not transport count.

## 7. Canonical identities required before verification

Before any positive result, the implementation must derive and independently verify canonical identities for:

```text
user_request_sha256
formation_state_sha256
review_material_sha256
decision_request_sha256
draft_sha256
authority_requirement_sha256
evidence_trust_profile_sha256
executor_commit
formation_profile_sha256
canonical_task_sha256
```

Canonical serialization must be deterministic and regression-tested.

A supplied hash never substitutes for verifying the source object it claims to identify.

## 8. Verification algorithm

A compliant verifier must fail closed unless it can independently establish every step:

```text
1. Verify exact Executor repository + commit identity.
2. Verify formation profile and canonical task tracked at that commit.
3. Establish non-caller-constructable Verified Formation State or independently reconstruct it.
4. Verify current formation status is AWAITING_VERIFIED_HUMAN_AUTHORIZATION.
5. Recompute current draft identity.
6. Recompute review-material identity.
7. Recompute decision-request identity.
8. Resolve canonical REQUEST_INTENT authority requirement from superior sources.
9. Resolve canonical evidence trust profile from superior sources.
10. Verify request-origin evidence using only that canonical trust profile.
11. Verify decision-event evidence using only that canonical trust profile.
12. Verify request-originator subject binding == decision-actor subject binding.
13. Verify decision == ACCEPT.
14. Verify decision event binds to this exact decision request.
15. Verify decision request binds to this exact review material and draft.
16. Verify current draft identity still equals the draft intended for future freeze.
17. Verify evidence freshness / validity required by the canonical trust profile.
```

Any missing, unknown, stale, ambiguous or mismatched fact produces `BLOCKED`.

There is no permissive fallback.

## 9. Minimal successful result

Success may be represented as:

```text
schema_version: executor-verified-human-authority/1.0
status: VERIFIED_HUMAN_AUTHORITY
authority_dimension: REQUEST_INTENT
authority_class: REQUEST_INTENT_OWNER
request_id
request_originator_subject_binding
decision_actor_subject_binding
decision: ACCEPT
decision_event_id
user_request_sha256
formation_state_sha256
review_material_sha256
decision_request_sha256
draft_sha256
authority_requirement_sha256
evidence_trust_profile_sha256
formation_profile_sha256
canonical_task_sha256
executor_commit
verified_evidence_refs[]
verification_time / freshness result
```

But the serialized result is **not itself proof**.

```text
VALID VERIFIED-RESULT JSON
        !=
VERIFIED AUTHORITY FACT
```

A future Freeze Gate may trust the positive result only if one of these models is used:

### Model A — non-caller-constructable verification snapshot

The positive verification object can only be constructed by the trusted verifier after all checks above, using an internal proof capability analogous to the existing verified policy-snapshot pattern.

### Model B — independent Freeze Gate re-verification

The Freeze Gate receives the external evidence and canonical source identities and independently repeats the authority verification before freeze.

A plain caller-constructable dataclass/dict with `status="VERIFIED_HUMAN_AUTHORITY"` is forbidden as a trust boundary.

The result also must not expose general execution authority.

## 10. Negative output

Any failed or unresolved check returns only a fail-closed result such as:

```text
status: BLOCKED
reason_codes[]
verified_human_authority: false
frozen_contract: absent
execution_authority: absent
```

Unknown never degrades into inferred approval.

## 11. State transition contract

Allowed future transition:

```text
AWAITING_VERIFIED_HUMAN_AUTHORIZATION
        ↓
trusted verification boundary
        ↓
VERIFIED_HUMAN_AUTHORITY
        ↓
separate future Freeze Gate
        ↓
AUTHORIZED_AND_FROZEN
```

Forbidden shortcuts include:

```text
caller/model/local receipt says ACCEPT -> freeze
caller-built formation request says AWAITING -> verify
caller-built result says VERIFIED -> freeze
```

## 12. Human Decision Receipt relationship

A Human Decision Receipt remains a bounded local claim container.

```text
VALID HUMAN DECISION RECEIPT
        !=
VERIFIED HUMAN AUTHORITY
```

The receipt may point to evidence. It may not select which evidence source, issuer, verifier or trust root is acceptable.

```text
EVIDENCE REF != TRUST SELECTOR
```

## 13. Idempotent revalidation

No global one-time human-decision receipt ledger is introduced.

```text
same immutable formation/request/decision/review/draft/trust identities
+ external evidence still valid
=
same verified authority fact
```

But:

```text
same receipt/evidence + different identity/context
=
BLOCKED
```

Exactly-once consumption of later consequential actions remains separate.

## 14. Failure modes implementation must close

The first implementation cannot be accepted until adversarial tests close at least:

```text
F-4  Self-Declared Decision Authority
F-5  Approval Drift
F-6  Authorization Generalization / Delegation Drift
F-7  Authority Substitution
F-8  Authority Requirement Injection / Downgrade
F-9  Authority Policy Source Substitution
F-10 Evidence Self-Issuance
F-11 Issuer Substitution / Provider Shopping
F-12 Evidence Scope Drift
F-13 Verifier / Trust Profile Substitution
F-14 Evidence Freshness / Revocation Drift
F-15 Authority Dimension Conflation
F-16 Verified Result Self-Minting
F-17 Formation State / Authorization Request Forgery
F-18 Cross-Issuer Subject Collision / False Equivalence
```

### F-16 — Verified Result Self-Minting

```text
caller constructs {status: VERIFIED_HUMAN_AUTHORITY}
→ Freeze Gate trusts structure
→ freeze
```

Invariant:

```text
VERIFICATION RESULT STRUCTURE != VERIFIED AUTHORITY FACT
```

### F-17 — Formation State / Authorization Request Forgery

```text
caller constructs plausible AWAITING request + draft hash
→ human-authority verifier trusts upstream labels
→ verifies real human evidence against forged formation state
→ positive result
```

Invariant:

```text
FORMATION REQUEST STRUCTURE != VERIFIED FORMATION STATE
```

### F-18 — Cross-Issuer Subject Collision / False Equivalence

```text
issuer A subject "123" originates request
issuer B subject "123" approves
bare strings compare equal
→ false same-person conclusion
```

Invariant:

```text
SUBJECT STRING EQUALITY != VERIFIED IDENTITY EQUALITY
```

For the first slice, origin and decision must resolve inside the same canonical subject namespace/trust profile.

Additional mandatory attacks:

```text
User A originates request; User B genuinely ACCEPTS
valid request-origin evidence + fabricated decision event
valid decision event + fabricated request-origin evidence
correct actor + wrong decision request
correct actor + modified review material
correct actor + modified draft
correct evidence + wrong Executor commit
provider unavailable -> attempted fallback
caller supplies alternate verifier/trust profile
local decision adapter presented as sole evidence
caller supplies forged AWAITING formation request
caller supplies forged VERIFIED result
same bare subject id from different issuers
VERIFIED_HUMAN_AUTHORITY reused as WRITE/MERGE/DEPLOY authority
```

Expected for every unauthorized or unresolved case:

```text
BLOCKED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 15. Explicit non-goals

This first contract does not implement or define:

- organization hierarchy;
- RBAC / ABAC;
- repository-owner discovery;
- production/deployment approver roles;
- delegation graph;
- standing delegation;
- quorum / multi-party approval;
- approval chains;
- enterprise IAM;
- cross-provider identity federation or account linking;
- OAuth/OIDC provider choice;
- passkeys;
- hardware keys;
- signature/PKI/HMAC format;
- human-approval UI;
- database or distributed ledger;
- global one-time receipt consumption;
- downstream write/merge/deploy authorization;
- automatic approval;
- model-generated authority.

## 16. Current implementation gaps

`main` already provides the upstream phase-1 formation kernel and fail-closed stop at `AWAITING_VERIFIED_HUMAN_AUTHORIZATION`.

The following are **not yet implemented or canonically machine-readable on `main`**:

```text
complete independently verifiable formation snapshot/export
externally rooted request-origin identity
externally verified decision-event evidence
machine-readable REQUEST_INTENT_OWNER authority requirement
machine-readable canonical evidence trust profile
non-caller-constructable human-evidence trust snapshot
verified-human-authority verifier/snapshot
Freeze Gate consuming/re-verifying that verified fact
AUTHORIZED_AND_FROZEN transition
```

The current `executor-human-formation-authorization-request/1.0` is therefore an upstream product artifact, not yet a sufficient independent proof object for this boundary.

This document must not be used to claim missing capabilities exist.

## 17. Acceptance gate for implementation work

Implementation may start only after this contract is adversarially reviewed and explicitly accepted as the implementation boundary.

Future code must remain narrow:

```text
verified formation state
+ canonical authority/trust resolution
+ external origin/decision evidence verification
+ exact identity comparison
-> trusted VERIFIED fact or BLOCKED
```

It must not introduce a second IAM, provider marketplace, general delegation, cross-provider identity graph or broad authorization platform.

The first implementation success criterion is:

> **Executor can independently establish that the externally verified owner of one exact request explicitly ACCEPTED one exact decision request for one exact reviewed draft, under one canonical trust profile, while granting no authority beyond that formation transition — and neither the upstream formation state nor the downstream VERIFIED result can be forged by caller-controlled object construction.**
