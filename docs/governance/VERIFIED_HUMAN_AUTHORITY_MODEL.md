---
document: "Verified Human Authority Model"
version: "0.3"
status: "DIRECTION ACCEPTED / DRAFT PENDING MERGE"
date: "2026-08-09"
scope: "evidence, identity, intent ownership and bounded human authorization of an exact contract"
repository: "litrgratis-pixel/Executor"
---

# Verified Human Authority Model v0.3

## 1. Purpose

This document defines what Executor may mean when it claims that a human authorized a contract.

It does not implement authentication, UI, signatures, identity providers, sessions, IAM, evidence providers or executable contract freezing.

Core rules:

```text
HUMAN ACTION != VERIFIED HUMAN AUTHORITY
AUTHENTICATION != AUTHORIZATION
AI INTERPRETATION != USER INTENT
AUTHORIZATION MUST BIND TO EXACT CONTRACT IDENTITY
HUMAN AUTHORITY IS BOUNDED AUTHORIZATION, NOT GENERAL DELEGATION
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

A human decision becomes formation authority only when external evidence binds the correct verified actor, the exact decision, the exact reviewed contract identity and the authority dimension that owns that transition.

## 2. Why this boundary exists

PR #50 closed F-4 by removing process-local self-declared human authority.

Rejected pattern:

```text
caller
  -> HumanDecisionReceipt(authority_source="HUMAN_AUTHORITY")
  -> AUTHORIZED_AND_FROZEN
```

A label is not proof that a human made a decision.

The deeper problem is now:

> Who has authority to approve what this user request means, and how can that exact decision be independently established without accidentally granting authority for later consequential actions?

## 3. Separate objects

```text
USER REQUEST
!= DRAFT CONTRACT
!= DECISION REQUEST
!= REVIEW MATERIAL
!= HUMAN ACTION
!= HUMAN DECISION RECEIPT
!= VERIFIED AUTHORITY EVIDENCE
!= AUTHORIZED / FROZEN CONTRACT
```

No downstream object becomes trusted merely because an earlier object exists.

## 4. Intent authority is a distinct authority dimension

Contract formation answers:

> Does this exact draft faithfully represent the goal/request that the human wants Executor to execute?

That is an **intent authority** question.

It is not automatically a resource/action authority question.

Therefore:

```text
APPROVAL OF CONTRACT MEANING
    !=
PERMISSION TO WRITE / MERGE / DEPLOY / USE SECRETS
```

and:

```text
RESOURCE ADMINISTRATION AUTHORITY
    !=
OWNERSHIP OF USER INTENT
```

For the first `REQUEST_TO_CONTRACT_001` slice, the narrowest defensible formation authority is the externally verified owner/originator of the governed request/goal.

The first slice SHOULD therefore require a canonical authority class equivalent to:

```text
REQUEST_INTENT_OWNER
```

The label is not yet a frozen schema value.

Meaning:

```text
the actor who may ACCEPT the formed contract
must be the same externally verified principal
that originated/owns the governed user request
```

If a future project needs project-owner, organization-admin, quorum or delegated approval instead, that is a separate explicit superior governance requirement.

## 5. Request-origin identity is not self-declared

The statement:

```text
request_originator = USER
```

is not evidence.

The original request must carry or resolve to externally verified originator identity evidence from a superior trust boundary.

Formation may preserve that binding.

Formation may not invent, replace or upgrade it.

For the first slice, freeze ultimately requires:

```text
VERIFIED REQUEST ORIGINATOR
        ==
VERIFIED DECISION ACTOR
```

plus exact decision/request/contract bindings.

## 6. Human review material

The human must receive meaningful review material including at least:

```text
original user request
understood objective
repository/input identity
proposed write scope
protected material
success conditions
discovered but out-of-scope work
unresolved assumptions
critical critique findings
exact draft contract identity
required formation authority meaning
```

Readable meaning without immutable identity is insufficient.

A hash without readable meaning is also insufficient.

## 7. Human Decision Receipt is not proof

A Human Decision Receipt records one bounded decision event.

It may bind:

```text
decision_request_id
decision_request_sha256
actor subject
decision ACCEPT | MODIFY | REJECT
reviewed_contract_sha256
review_material_sha256
authority_requirement_sha256
evidence_trust_profile_sha256
decision event identity
evidence references
```

But:

```text
VALID RECEIPT STRUCTURE != VERIFIED HUMAN AUTHORITY
```

Receipt fields are claims until verified against external evidence and canonical authority policy.

## 8. Authority requirement, ownership and evidence source remain separate

```text
AUTHORITY REQUIREMENT
  what must be proved

AUTHORITY OWNERSHIP
  who currently possesses that authority

AUTHORITY EVIDENCE SOURCE
  which external source is trusted to prove it
```

Therefore:

```text
AUTHORITY REQUIREMENT
!= AUTHORITY OWNERSHIP
!= AUTHORITY EVIDENCE SOURCE
```

Executor must not become a parallel IAM system.

## 9. Canonical authority source rule

Required authority and accepted evidence trust must come from canonical superior governance.

Caller/model/formation output may not select or downgrade them.

The current Executor hierarchy remains:

```text
executor_policy
> project_contract
> task_contract
> authoritative_source
> untrusted_repository_data
> generated_data
```

Lower layers may add constraints but cannot remove superior ones.

Valid-looking policy content from the wrong source is not authority.

## 10. External evidence must prove event and authority fact

The decision adapter is not the root of truth merely because it observed a button/click/action.

External evidence must collectively establish:

### Decision Event Evidence

```text
verified actor subject
exact decision value
exact decision request/event binding
freshness/validity
```

### Authority Ownership / Entitlement Evidence

For the first slice:

```text
verified actor is the verified request/goal owner
```

For later slices, another canonical authority class/context may be required.

One artifact may prove both classes. Multiple artifacts may jointly prove them.

## 11. Evidence source is canonical, not caller-selected

`authority_evidence_ref` is only a locator.

It does not choose:

```text
issuer
verifier
trust root
network origin
key set
authority class
```

The accepted evidence trust profile must come from canonical superior policy/project governance.

Caller/model/decision adapter may not shop among providers or fall back to a weaker verifier.

Executor-local components may verify externally rooted evidence but cannot be the sole root that issues the human-authority evidence they accept.

## 12. Exact contract identity rule

Central invariant:

```text
verified reviewed_contract_sha256
== current_draft_contract_sha256
== contract_sha256_to_be_frozen
```

Any mismatch blocks freeze.

Approval of A is not approval of B.

## 13. Bounded authorization rule

Correct meaning:

```text
VERIFIED ACTOR
  makes DECISION D
  for REQUEST R
  covering CONTRACT C
  after REVIEW MATERIAL M
```

Incorrect meaning:

```text
actor once approved something
-> Executor is generally trusted
-> future contracts/actions inherit approval
```

Normal contract approval never creates standing delegation.

## 14. Failure-mode chain

### F-4 — Self-Declared Decision Authority

Caller says `human approved` without verified evidence.

### F-5 — Approval Drift

Human approved A; system later freezes B.

### F-6 — Authorization Generalization / Delegation Drift

Approval of A becomes standing trust for B/Y.

### F-7 — Authority Substitution

A real decision from the wrong actor/account/authority context is accepted as equivalent.

### F-8 — Authority Requirement Injection / Downgrade

The system asks for weaker/different authority than canonical superior governance requires.

### F-9 — Authority Policy Source Substitution

A valid-looking policy/project artifact from the wrong repository/commit/path/source is accepted as canonical.

### F-10 — Evidence Self-Issuance

Executor or its local formation/decision/freeze component issues the sole authority evidence it later accepts.

### F-11 — Issuer Substitution / Provider Shopping

Caller/adapter selects another issuer/provider or tries providers until one returns YES.

### F-12 — Evidence Scope Drift

Real evidence for another request/project/org/tenant/time is reused here.

### F-13 — Verifier / Trust Profile Substitution

A plausible issuer is checked with a caller-selected permissive verifier, trust root or discovery endpoint.

### F-14 — Evidence Freshness / Revocation Drift

Evidence that was once valid is treated as valid for current freeze after it becomes stale/revoked/unknown.

### F-15 — Authority Dimension Conflation

Intent-owner approval is reused as action/resource authority, or resource/admin authority is treated as ownership of the user's intent.

## 15. Required invariants from F-4 through F-15

```text
SELF-DECLARED HUMAN AUTHORITY != VERIFIED HUMAN AUTHORITY
APPROVAL OF A != APPROVAL OF B
AUTHORIZATION != DELEGATION
"SOME HUMAN APPROVED" != "THE REQUIRED AUTHORITY APPROVED"
LOWER TRUST MAY NOT WEAKEN HIGHER TRUST
VALID POLICY CONTENT != CANONICAL POLICY AUTHORITY
EXECUTOR CANNOT BE ITS OWN HUMAN-AUTHORITY ROOT
EVIDENCE REF != TRUST SELECTOR
AUTHORITY EVIDENCE MUST BIND TO EXACT DECISION CONTEXT
VALID ONCE != VALID FOR CURRENT FREEZE
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

## 16. What verified formation authority proves

For the first slice, successful verification may prove only:

```text
The externally verified owner/originator of request Q
made decision ACCEPT
for exact decision request R
covering exact contract C
using exact review material M
under the canonical evidence trust profile
while required evidence was valid.
```

It does not prove:

```text
technical correctness
execution success
resource/action permission
merge permission
deploy permission
product acceptance
general delegation
future contract authorization
```

## 17. First-slice minimal claim set

Without choosing a provider technology, the first controlled evidence trust profile must be capable of proving:

```text
verified_request_originator_subject
verified_decision_actor_subject
originator == decision_actor
exact decision == ACCEPT
exact decision_request identity
exact decision-event identity
canonical external trust source identity
required freshness/validity at freeze
```

This is intentionally smaller than enterprise IAM.

If implementation cannot prove these properties without caller self-declaration, it must remain blocked.

## 18. Adversarial requirements before implementation

Future implementation must fail closed on at least:

```text
forged request-originator identity
forged decision receipt
wrong decision actor
wrong draft/review/request hash
stale approval after modification
standing-trust reuse
wrong authority requirement
wrong policy source
self-issued evidence
issuer substitution
provider shopping/fallback
wrong trust verifier/root
cross-context evidence
stale/revoked/unknown evidence
intent approval reused as WRITE/MERGE/DEPLOY authority
resource admin used to silently redefine user intent
```

Expected:

```text
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 19. Implementation non-goals

This model still does not choose:

```text
OAuth/OIDC
passkeys
GitHub approval
hardware key
signature format
PKI/HMAC
identity provider
database/ledger
organization directory
quorum
delegation implementation
UI/button semantics
```

Technology follows accepted authority semantics, not the reverse.

## 20. Model checkpoint

```text
PR #51: DRAFT
DIRECTION: ACCEPTED
MERGE: NO
IMPLEMENTATION: NOT STARTED
```

The model now incorporates the adversarial findings from PR #52 through F-15 and explicitly separates intent authority from downstream action authority.

Before any implementation begins, the stacked design in PR #52 must still be reviewed and accepted separately.
