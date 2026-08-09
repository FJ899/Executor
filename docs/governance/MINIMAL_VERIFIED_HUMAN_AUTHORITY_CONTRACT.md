---
document: "Minimal Verified Human Authority Implementation Contract"
version: "0.1"
status: "DRAFT / NON-EXECUTABLE IMPLEMENTATION CONTRACT"
date: "2026-08-09"
scope: "first REQUEST_TO_CONTRACT_001 verified-human-authority boundary between formation decision request and future freeze gate"
repository: "litrgratis-pixel/Executor"
depends_on:
  - "docs/governance/VERIFIED_HUMAN_AUTHORITY_MODEL.md"
  - "docs/governance/MINIMAL_HUMAN_DECISION_RECEIPT_DESIGN.md"
---

# Minimal Verified Human Authority Implementation Contract v0.1

## 1. Purpose

This document defines the smallest implementation boundary that may later establish verified human authority for the first `REQUEST_TO_CONTRACT_001` slice.

It is **not implementation**. It does not select a UI, identity provider, OAuth/OIDC flow, signature scheme, passkey, GitHub approval mechanism, IAM database, organization model or receipt ledger.

The boundary exists only to answer this first-slice question:

> Did the same externally verified principal who originated/owns this exact user request explicitly ACCEPT this exact decision request for this exact reviewed draft, under the canonical trust rules, with evidence that is still valid for freeze?

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
VALID EVIDENCE
        =
VERIFIED HUMAN AUTHORITY FOR CONTRACT FORMATION
```

This result concerns **intent authority only**.

```text
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

A successful result from this boundary does not itself authorize repository writes, merge, deploy, network, secret use or any other consequential action.

## 2. Existing formation boundary is the upstream input

`RequestToContract001` already stops at:

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

The future human-authority boundary must consume this existing formation output rather than inventing a parallel request-to-contract representation.

The current request is not yet sufficient by itself to prove verified human authority. In particular, the implementation must derive or add machine-verifiable bindings for the exact decision-request identity, review-material identity, externally rooted request-origin identity, canonical authority requirement and canonical evidence-trust profile.

## 3. Authority dimension for the first slice

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

This contract does not define organization administrator, repository owner, production approver, security approver, delegated approver or quorum semantics.

If later product slices require those authorities, they require separate canonical requirements and separate evidence semantics.

## 4. Required input classes

The boundary may evaluate a decision only when it has all of the following input classes.

### A. Formation Authorization Request

Must come from the already-verified formation state and bind at least:

```text
request_id
verbatim user request / canonical user-request digest
executor repository + exact executor commit
formation profile id + sha256
canonical task sha256
current draft sha256
allowed decisions
exact review material / decision surface
```

The verifier recomputes identities from canonical input. It must not trust caller-supplied duplicate hash fields when the source material is available for recomputation.

### B. Canonical Authority Requirement Snapshot

Must resolve from verified superior governance, never from caller/model/receipt input.

Minimum semantics for this slice:

```text
authority_dimension: REQUEST_INTENT
authority_class: REQUEST_INTENT_OWNER
required_subject_relation: REQUEST_ORIGINATOR_EQUALS_DECISION_ACTOR
source_bindings[]
executor_commit
authority_requirement_sha256
```

The snapshot must follow the existing non-caller-constructable verified-snapshot principle already used by Executor policy loading.

### C. Canonical Evidence Trust Snapshot

Must resolve from canonical superior policy/project sources.

Minimum semantics:

```text
trust_profile_id
allowed external issuer / trust-root identity
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
verified request-originator subject
exact request event / request identity binding
binding to the request represented by the formation authorization request
canonical trusted source identity
required validity / freshness
```

A process-local field such as `originator = USER` is not evidence.

### E. Decision-Event Evidence

External evidence must establish at least:

```text
verified decision-actor subject
decision == ACCEPT
exact decision-event identity
exact decision-request identity
required validity / freshness
canonical trusted source identity
```

A local `user_clicked_button = true` event is not sufficient proof by itself.

The request-origin and decision-event claims may be carried by one externally verifiable artifact or by multiple artifacts. The contract constrains claims, not transport count.

## 5. Canonical identities required before verification

Before any positive result, the implementation must derive canonical identities for:

```text
user_request_sha256
review_material_sha256
decision_request_sha256
draft_sha256
authority_requirement_sha256
evidence_trust_profile_sha256
executor_commit
formation_profile_sha256
canonical_task_sha256
```

The exact canonical serialization must be deterministic and testable.

Where current `executor-human-formation-authorization-request/1.0` does not carry an explicit hash field, the future implementation may either:

1. deterministically recompute it from the bound source object; or
2. evolve the formation request schema to include it while still recomputing it at verification.

A supplied hash never substitutes for verifying the source object it claims to identify.

## 6. Verification algorithm

A future compliant verifier must fail closed unless it can independently establish every step below.

```text
1. Verify exact Executor repository + commit identity.
2. Verify the formation profile and canonical task tracked at that commit.
3. Verify the current formation state is AWAITING_VERIFIED_HUMAN_AUTHORIZATION.
4. Recompute the current draft identity.
5. Recompute the review-material identity.
6. Recompute the decision-request identity.
7. Resolve the canonical REQUEST_INTENT authority requirement from superior sources.
8. Resolve the canonical evidence trust profile from superior sources.
9. Verify request-origin evidence using only the canonical trust profile.
10. Verify decision-event evidence using only the canonical trust profile.
11. Verify request-originator subject == decision-actor subject.
12. Verify decision == ACCEPT.
13. Verify the decision event binds to this exact decision request.
14. Verify the decision request binds to this exact review material and draft.
15. Verify current draft identity still equals the draft intended for future freeze.
16. Verify evidence freshness / validity required by the canonical trust profile.
```

Any missing, unknown, stale, ambiguous or mismatched required fact produces `BLOCKED`.

There is no permissive fallback.

## 7. Minimal output contract

The successful output is a **verification result**, not a permission token and not a frozen contract.

Conceptual schema:

```text
schema_version: executor-verified-human-authority/1.0
status: VERIFIED_HUMAN_AUTHORITY
authority_dimension: REQUEST_INTENT
authority_class: REQUEST_INTENT_OWNER
request_id
request_originator_subject
decision_actor_subject
decision: ACCEPT
decision_event_id
user_request_sha256
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

Required equality:

```text
request_originator_subject
        ==
decision_actor_subject
```

The result may be consumed only by a separate future Freeze Gate that rechecks exact current identities.

It must not itself expose general execution authority.

## 8. Negative output

Any failed or unresolved check returns only a fail-closed result such as:

```text
status: BLOCKED
reason_codes[]
verified_human_authority: false
frozen_contract: absent
execution_authority: absent
```

The boundary must never downgrade an unknown result into an inferred approval.

## 9. State transition contract

Allowed future transition:

```text
AWAITING_VERIFIED_HUMAN_AUTHORIZATION
        ↓
VERIFIED_HUMAN_AUTHORITY
        ↓
FUTURE FREEZE GATE
        ↓
AUTHORIZED_AND_FROZEN
```

Forbidden shortcut:

```text
AWAITING_VERIFIED_HUMAN_AUTHORIZATION
        ↓
caller/model/local receipt says ACCEPT
        ↓
AUTHORIZED_AND_FROZEN
```

The verification result and Freeze Gate remain separate responsibilities.

## 10. Human Decision Receipt relationship

A Human Decision Receipt may be a bounded local record containing exact hashes and evidence references.

It remains only a claim container until this boundary verifies the required external evidence under the canonical trust snapshot.

Therefore:

```text
VALID HUMAN DECISION RECEIPT
        !=
VERIFIED HUMAN AUTHORITY
```

and:

```text
EVIDENCE REF != TRUST SELECTOR
```

The receipt may point to evidence. It may not choose which evidence source, issuer, verifier or trust root is acceptable.

## 11. Idempotent revalidation

No global one-time human-decision receipt ledger is introduced by this contract.

```text
same immutable request + same immutable decision + same exact identities
+ evidence still valid under the canonical trust profile
=
same verified authority fact
```

But:

```text
same receipt/evidence + different request/draft/review/requirement/trust identity
=
BLOCKED
```

Exactly-once consumption of later consequential actions remains a separate action-authorization property.

## 12. Failure modes that implementation must close

The first implementation cannot be accepted until adversarial tests demonstrate fail-closed behavior for at least:

```text
F-4  self-declared decision authority
F-5  approval drift
F-6  delegation/generalization drift
F-7  authority substitution
F-8  authority requirement injection/downgrade
F-9  authority policy source substitution
F-10 evidence self-issuance
F-11 issuer substitution/provider shopping
F-12 evidence scope drift
F-13 verifier/trust-profile substitution
F-14 evidence freshness/revocation drift
F-15 intent authority confused with resource/action authority
```

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
VERIFIED_HUMAN_AUTHORITY reused as WRITE/MERGE/DEPLOY authority
```

Expected in every unauthorized or unresolved case:

```text
BLOCKED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 13. Explicit non-goals

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

## 14. Current implementation gaps

At the time of this contract draft, `main` already provides the upstream phase-1 formation boundary and fail-closed stop at `AWAITING_VERIFIED_HUMAN_AUTHORIZATION`.

The following are **not yet implemented or canonically machine-readable on `main`**:

```text
externally rooted request-origin identity
externally verified decision-event evidence
machine-readable REQUEST_INTENT_OWNER authority requirement
machine-readable canonical evidence trust profile
non-caller-constructable human-evidence trust snapshot
verified-human-authority result validator
Freeze Gate consuming that verified result
AUTHORIZED_AND_FROZEN transition
```

This document must not be used to claim those capabilities exist.

## 15. Acceptance gate for implementation work

Implementation may start only after this contract is reviewed adversarially and the project explicitly accepts its direction.

Code implementing the boundary must remain narrow:

```text
formation request input
+ canonical authority/trust resolution
+ external evidence verification
+ exact identity comparison
-> VERIFIED or BLOCKED
```

It must not introduce a second IAM, a provider marketplace, general delegation or a broad authorization platform.

The first implementation success criterion is not:

> "human approval works"

It is:

> **Executor can independently establish that the externally verified owner of one exact request explicitly ACCEPTED one exact decision request for one exact reviewed draft, under one canonical trust profile, while granting no authority beyond that formation transition.**
