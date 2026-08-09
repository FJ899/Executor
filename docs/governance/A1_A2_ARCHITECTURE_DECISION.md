---
document: "A1 vs A2 Architecture Decision"
version: "0.1"
status: "DRAFT / ADVERSARIAL ARCHITECTURE REVIEW / NO SELECTION"
date: "2026-08-09"
scope: "placement of trusted request-origin evidence relative to the Executor user front door"
repository: "litrgratis-pixel/Executor"
depends_on:
  - "docs/governance/VERIFIED_HUMAN_AUTHORITY_MODEL.md"
  - "docs/governance/MINIMAL_HUMAN_DECISION_RECEIPT_DESIGN.md"
  - "docs/governance/MINIMAL_VERIFIED_HUMAN_AUTHORITY_CONTRACT.md"
  - "docs/governance/MINIMAL_EXTERNAL_TRUST_BOUNDARY_DESIGN.md"
  - "docs/governance/TRUST_TECHNOLOGY_COMPARISON.md"
  - "docs/governance/PATTERN_A_TECHNOLOGY_EVALUATION.md"
---

# A1 vs A2 Architecture Decision v0.1

## 1. Purpose

This document does **not** select A1, A2, a provider or an implementation.

It attacks the architectural placement of the first externally rooted fact about human intent.

The decision question is:

> **Where must the trusted request-origin event be created so that Executor can preserve the product front door while still independently proving who originated the exact governed request?**

This is not a provider-selection question.

It is a product/trust-boundary placement question.

## 2. Fixed invariants

Neither A1 nor A2 may weaken the already accepted model.

```text
USER OWNS THE GOAL
REQUEST != CONTRACT
AI INTERPRETATION != USER INTENT
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
EXECUTOR VERIFIES AUTHORITY != EXECUTOR OWNS IDENTITY AUTHORITY
EVIDENCE REF != TRUST SELECTOR
LATER AUTHENTICATION != PROOF OF EARLIER REQUEST ORIGINATION
EVENT IDENTITY != EVENT CONTENT IDENTITY
PROVIDER-VALID EVENT != DIRECT HUMAN ACTION
```

Additional product invariant introduced by this review:

> **FRONT DOOR OWNERSHIP MUST BE EXPLICIT.**

A security mechanism may change the product front door, but that change must be an explicit product architecture decision rather than an accidental consequence of provider selection.

## 3. F-24 — Front Door Ownership Drift

Failure:

```text
initial product model:
USER -> EXECUTOR

security integration added:
USER -> EXTERNAL APPROVAL / TRUST DOMAIN -> EXECUTOR

later system behavior:
external domain owns request creation, interaction flow and user entry
Executor primarily consumes already-governed work
```

The resulting architecture may be valid.

The failure is allowing this transition to happen implicitly while still claiming the original product boundary.

Invariant:

```text
FRONT DOOR OWNERSHIP
MUST BE EXPLICIT
```

Required consequence:

- A1 must explicitly declare the external trust domain as the governed request-entry boundary.
- A2 must prove that Executor remains the user interaction front door while an external domain provides only the required trust facts.

## 4. A1 — Externalized Governed Request Intake

Canonical shape:

```text
HUMAN
  ↓
EXTERNAL TRUST DOMAIN
  authenticates principal P
  directly records exact request event R
  preserves exact request content/revision
  ↓
EXECUTOR
  imports verified request-origin evidence
  forms / critiques contract
  ↓
EXTERNAL TRUST DOMAIN
  presents exact decision request Q
  records direct human ACCEPT event D
  ↓
EXECUTOR VERIFIER
  proves P originated R
  proves P accepted Q
  proves Q binds current review/draft
```

### A1 trust strengths

A1 can keep FACT A and FACT B inside one external identity/event domain:

```text
FACT A: P originated R
FACT B: P accepted Q
```

This naturally reduces:

- retroactive request-origin attribution;
- cross-issuer subject matching;
- split trust-root ambiguity;
- Executor identity ownership.

### A1 product cost

A1 changes the governed entry path from:

```text
USER -> EXECUTOR
```

to:

```text
USER -> EXTERNAL TRUST DOMAIN -> EXECUTOR
```

Executor may still provide execution, contract formation, critique and evidence UX, but it is no longer the sole origin surface for a governed request.

This is a product architecture change, not a mere authentication implementation detail.

### A1 additional constraint — external capture must not redefine intent

The external domain may own the event truth without owning the user's goal.

It must preserve the exact user-originated request content supplied to Executor.

Forbidden shape:

```text
human writes request A
external domain normalizes / rewrites / interprets A -> B
Executor receives only B
B is later treated as the user's original intent
```

Therefore A1 requires an immutable/raw request representation or equivalent exact origin-content commitment.

External event ownership does not grant the external system semantic ownership of user intent.

## 5. A2 — External Origin Attestation at Executor Intake

Naive A2 is insufficient.

Rejected naive shape:

```text
HUMAN types request in Executor
        ↓
external system authenticates P
        ↓
Executor locally says authentication applies to request hash H
```

This would not prove that P directly attested exact H.

It can recreate F-21/F-23 at intake.

### Strengthened A2 required shape

A2 survives the attack only if intake itself contains a transaction-specific external human-action event:

```text
HUMAN
  ↓
EXECUTOR FRONT DOOR
  captures exact raw request A
  derives canonical request identity H(A)
  ↓
CANONICAL EXTERNAL TRUST DOMAIN
  presents / binds exact request identity H(A)
  obtains direct principal action from P
  records immutable/tamper-evident request-origin event R
  ↓
EXECUTOR
  accepts R as the verified origin fact
  forms / critiques contract
  derives exact decision request Q
  ↓
SAME CANONICAL EXTERNAL TRUST DOMAIN
  presents exact Q
  obtains direct principal ACCEPT from P
  records decision event D
  ↓
EXECUTOR VERIFIER
  proves R.subject_binding == D.subject_binding
  proves R binds exact A
  proves D binds exact Q
  proves Q binds current review/draft
```

The external trust domain is therefore invoked twice:

1. request-origin attestation;
2. later contract-meaning decision.

But Executor remains the interaction front door.

### Why one canonical trust domain is preferred in the first slice

Using provider/domain X for request origin and provider/domain Y for decision approval would immediately require cross-domain identity equivalence.

That reopens F-18 and account federation.

The first slice should therefore require:

```text
REQUEST ORIGIN TRUST DOMAIN
        ==
DECISION TRUST DOMAIN
```

unless a later separately governed identity-federation model is explicitly introduced.

This is not provider selection. It is a first-slice trust constraint.

## 6. A1 vs A2 invariant matrix

Evaluation vocabulary:

```text
PASS
The architecture naturally supports the property if the external mechanism satisfies the fixed trust requirements.

CONDITIONAL
The architecture can satisfy the property only if an additional explicit boundary is implemented and verified.

FAIL / PRODUCT CHANGE
The architecture intentionally changes the current product boundary rather than preserving it.
```

| Requirement | A1 — externalized intake | A2 — external attestation at Executor intake |
|---|---|---|
| Externally rooted request-origin event | PASS | CONDITIONAL — requires direct transaction-specific origin attestation at intake |
| Exact request-content binding | PASS if external intake preserves immutable raw request/revision | CONDITIONAL — external origin event must bind exact canonical request identity |
| Direct human action provenance at request origin | PASS if provider distinguishes human vs service creation | CONDITIONAL — ordinary login is insufficient; direct principal attestation required |
| Same subject namespace for origin + decision | PASS naturally if same domain owns both | PASS only if same canonical external trust domain is used for both first-slice events |
| Externally rooted decision event | PASS | PASS if same canonical external domain performs transaction-specific approval |
| Exact reviewed decision binding | PASS if external domain presents exact Q | PASS if external domain presents/binds exact Q |
| Executor independently verifies meaning of Q | PASS | PASS |
| Executor remains user/product front door | FAIL / PRODUCT CHANGE | PASS |
| External domain becomes governed request front door | YES, explicitly | NO |
| User remains owner of goal | PASS only if raw request is preserved and external domain does not semantically rewrite it | PASS; Executor still must preserve verbatim request and provenance |
| Executor avoids identity ownership | PASS | PASS |
| Cross-provider identity federation required | NO if one domain owns both events | NO if first slice uses same canonical domain for origin + decision |
| Trust-boundary composition complexity | LOWER | HIGHER — two external ceremonies around one Executor-centered flow |
| Natural fit with current USER -> EXECUTOR -> CONTRACT product model | LOW | HIGH |

## 7. Critical clarification — front door ownership != goal ownership

A1 moving the front door outside Executor would **not** make the external platform the owner of the human goal.

Goal ownership remains human.

However, the front door determines:

- where the original governed event is created;
- which interaction surface captures the verbatim request;
- which system becomes operationally mandatory before Executor can start;
- where user experience begins.

Therefore:

```text
GOAL OWNERSHIP = HUMAN
FRONT DOOR OWNERSHIP = PRODUCT ARCHITECTURE CHOICE
IDENTITY / EVENT TRUTH OWNERSHIP = EXTERNAL TRUST DOMAIN
```

These must not be conflated.

## 8. A2 attack — attestation must bind what the human actually originated

A2 must not use an external authentication event as a proxy for request-origin evidence.

Forbidden:

```text
P logs in / authenticates
Executor has request A
Executor binds P to A locally
```

Required:

```text
P performs an externally verifiable direct action
bound to exact immutable identity of A
```

The external mechanism does not need to understand Executor semantics.

It must prove:

```text
P directly attested request-origin transaction H(A)
```

Executor separately proves what H(A) corresponds to.

This mirrors the later decision model:

```text
external domain proves WHO acted + WHICH exact transaction
Executor proves WHAT that transaction means in canonical state
```

## 9. A1 attack — the cleanest security model can still be the wrong product model

A1 has fewer trust-composition edges.

That does not automatically make it the correct Executor architecture.

Security cleanliness cannot silently redefine the product into:

```text
external approval platform
        ↓
Executor worker
```

If A1 is ever selected, the product must explicitly accept that the governed request starts outside Executor.

Otherwise F-24 remains open even if all cryptographic/evidence checks pass.

## 10. A2 attack — preserving the front door has a real cost

A2 preserves:

```text
USER -> EXECUTOR -> CONTRACT
```

but only by adding a narrow external trust ceremony at request intake.

The product UX becomes conceptually:

```text
USER enters request in Executor
        ↓
external proof of request origination
        ↓
Executor forms draft contract
        ↓
external proof of exact human ACCEPT
        ↓
Freeze Gate later
```

This is more complex than A1.

The complexity is acceptable only if preserving Executor as product front door is an explicit product requirement.

## 11. Current adversarial result

Both A1 and strengthened A2 can, in principle, satisfy the accepted human-authority trust invariants.

The difference is no longer primarily assurance strength.

It is architecture placement:

```text
A1
simpler trust topology
but external trust domain owns governed request entry

A2
more trust choreography
but Executor remains the product front door
```

The naive version of A2 is rejected.

Only the strengthened version survives:

```text
EXECUTOR FRONT DOOR
+
DIRECT EXTERNAL ORIGIN ATTESTATION OF EXACT REQUEST
+
SAME EXTERNAL TRUST DOMAIN FOR LATER EXACT DECISION
```

No provider is selected by this conclusion.

## 12. Current recommendation for the next decision

Do not choose a provider yet.

The next user decision should be explicitly product-level:

> **Is preserving Executor as the governed user front door a canonical product requirement?**

If **NO**, A1 remains the simpler trust architecture and can be researched further.

If **YES**, A2 becomes the architecture to pursue, but only in the strengthened form defined above.

This is not a convenience preference.

It determines the system boundary.

## 13. Gate

```text
A1/A2 SELECTION: NOT MADE
PROVIDER: NOT SELECTED
IMPLEMENTATION: NOT STARTED
FRONT DOOR OWNERSHIP: EXPLICIT DECISION REQUIRED
F-24: DEFINED
NAIVE A2: REJECTED
STRENGTHENED A2: SURVIVES CURRENT DESIGN ATTACK
A1: SURVIVES CURRENT DESIGN ATTACK WITH EXPLICIT PRODUCT-BOUNDARY COST
MATURITY CLAIM: NONE
PRODUCT CLAIM: NONE
```

Until the front-door product decision is explicit:

```text
NO PROVIDER SELECTION
NO TRUST-BOUNDARY IMPLEMENTATION
NO AUTHORIZED_AND_FROZEN CLAIM
```
