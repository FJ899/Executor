---
document: "Minimal Human Decision Receipt Design"
version: "0.6"
status: "EXTERNAL AUTHORITY EVIDENCE TRUST REVIEW / IMPLEMENTATION BLOCKED"
date: "2026-08-09"
scope: "human decision record, canonical authority requirements, canonical evidence trust, external evidence and exact freeze verification"
repository: "litrgratis-pixel/Executor"
---

# Minimal Human Decision Receipt Design v0.6

```text
HUMAN DECISION RECEIPT != VERIFIED AUTHORITY EVIDENCE
AUTHENTICATION != AUTHORIZATION
AUTHORIZATION != DELEGATION
AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP
AUTHORITY REQUIREMENT != AUTHORITY EVIDENCE SOURCE
VALID POLICY CONTENT != CANONICAL POLICY AUTHORITY
EVIDENCE REF != TRUST SELECTOR
LOWER TRUST MAY NOT WEAKEN HIGHER TRUST
```

## 1. End-to-end authority boundary

```text
USER REQUEST
    ↓
FORMATION KERNEL
    exact draft + review + decision request
    ↓
CANONICAL AUTHORITY REQUIREMENT RESOLUTION
    derives non-bypassable requirements from verified superior sources
    ↓
CANONICAL EVIDENCE TRUST RESOLUTION
    derives which external trust profile may prove those requirements
    ↓
HUMAN DECISION ADAPTER
    presents exact material and records an observed action
    DOES NOT prove authority or choose the trusted issuer/verifier
    ↓
HUMAN DECISION RECEIPT
    local record of WHO / WHAT / exact bound identities / evidence refs
    IS NOT PROOF
    ↓
EXTERNAL EVIDENCE
    collectively proves decision event + authority entitlement
    ↓
FREEZE GATE
    re-verifies canonical sources, trust profile, evidence and exact identities
    ↓
AUTHORIZED_AND_FROZEN
```

No component may silently combine contract interpretation, authority-policy ownership, trust-provider selection, human-action capture, evidence issuance, evidence verification and freeze.

## 2. Existing Executor trust hierarchy remains the policy root

`EXECUTOR_POLICY.yaml` already defines:

```text
executor_policy
> project_contract
> task_contract
> authoritative_source
> untrusted_repository_data
> generated_data
```

The human-authority design reuses that hierarchy.

It does not introduce `ExecutorIAM`, `AuthorityPolicyStore`, an authority database or a second policy root.

For current GP001, the verified Executor repository identity, exact Executor commit, project bundle and tracked `EXECUTOR_POLICY.yaml` remain the canonical source boundary.

## 3. Requirement, ownership and evidence source are different things

```text
AUTHORITY REQUIREMENT
  says WHAT must be proved

AUTHORITY OWNERSHIP
  external system knows WHO currently possesses that authority

AUTHORITY EVIDENCE SOURCE
  says WHICH independently verifiable source may prove the required facts
```

Executor may know the first and the accepted proof mechanism without owning the mutable human/organization membership truth.

Core invariant:

> **AUTHORITY REQUIREMENT != AUTHORITY OWNERSHIP != AUTHORITY EVIDENCE SOURCE.**

## 4. Requirement ownership by trust layer

```text
EXECUTOR_POLICY
  system-wide trust hierarchy and non-bypassable minima
        ↓
PROJECT_CONTRACT / superior project governance
  project/domain authority requirements
        ↓
TASK CONTRACT
  may add narrower constraints
  may not remove or replace superior constraints
        ↓
FORMATION PROFILE
  process configuration/reference only
  not an authority-policy owner
```

Effective requirements compose conjunctively:

```text
SYSTEM REQUIREMENTS
AND PROJECT REQUIREMENTS
AND VALID ADDITIONAL TASK REQUIREMENTS
```

No `last-write-wins` or caller-selected downgrade semantics are allowed.

## 5. Canonical authority requirement identity

The resolved requirement is immutable verification material, not an IAM database.

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

It is bound into review material and the decision request.

## 6. Evidence Trust Profile

An Evidence Trust Profile answers:

> Which external source and verification rules are allowed to prove this authority requirement?

It is policy material, not mutable IAM membership.

Conceptual minimum semantics:

```text
trust_profile_id
allowed_issuer_identity / issuer namespace
verification_profile_id
required_claim_classes[]
required_context_bindings[]
freshness_policy
revocation/status policy if the chosen mechanism supports it
source_bindings[]
executor_commit
```

Canonical serialization yields:

```text
evidence_trust_profile_sha256
```

The trust profile itself must be resolved from canonical superior sources under the existing Executor trust hierarchy.

It may live directly in a superior policy/project contract or in an authoritative source referenced by that verified bundle.

A caller, model, formation profile or Human Decision Receipt may not create or select a new trust profile at runtime.

For the first implementation slice, one exact canonical external trust profile is preferred over multi-provider fallback logic.

## 7. Trust snapshot is not caller-constructable

The design follows the existing `ExecutionPolicySnapshot` principle:

```text
CALLER INPUT
    !=
VERIFIED TRUST SNAPSHOT
```

A future evidence-trust snapshot must be derivable only after verifying canonical repository/project/policy source identity.

Public execution/formation APIs must not accept runtime parameters such as:

```text
issuer=
verifier=
trust_profile=
verification_endpoint=
keyset_url=
allowed_issuers=
```

that could replace the canonical trust decision.

## 8. `authority_evidence_ref` is only a locator

The receipt may contain:

```text
authority_evidence_refs[]
```

but an evidence ref is not allowed to decide:

```text
which issuer is trusted
which verifier implementation runs
which network origin is trusted
which key set or trust root is used
which authority class is required
```

Core invariant:

> **EVIDENCE REF != TRUST SELECTOR.**

If a future implementation uses remote evidence retrieval, the canonical trust profile must constrain the provider/origin. A caller-supplied arbitrary URL is not an acceptable trust boundary.

If evidence contains an `issuer` or similar field, that value is checked against the canonical trust profile; it is not used to discover a new trusted provider.

## 9. Human Decision Receipt

The receipt remains a bounded local record, not proof and not a permission system.

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

Receipt fields do not become trusted merely because the schema is valid.

## 10. External evidence proves two distinct claim classes

The receipt records an observed decision event, but the decision adapter is not the final authority root for that fact.

External evidence must collectively establish two claim classes.

### A. Decision Event Evidence

Proves that the verified actor actually performed the recorded decision for the bound review/decision request.

Minimum semantic binding:

```text
actor subject
decision value
decision event identity
decision_request_sha256 or an equivalent exact bound identity
time/freshness required by the canonical trust profile
```

### B. Authority Entitlement Evidence

Proves that the same actor held the required authority in the required context.

Minimum semantic binding:

```text
actor subject
required authority class
required project/organization/tenant context
validity/freshness status
canonical issuer/trust profile identity
```

These claim classes may be carried by one externally verifiable artifact or multiple artifacts.

The Freeze Gate cares about the verified claims, not the number of files/tokens/messages carrying them.

## 11. Evidence context binding

External evidence must not be accepted merely because it proves:

```text
subject = Anna
role = ProductionApprover
```

It must satisfy the exact canonical context demanded by the decision request, including all applicable bindings such as:

```text
project / repository / organization / tenant
authority class
decision request identity
decision event identity
relevant validity interval
```

For current REQUEST_TO_CONTRACT_001, exact decision-request binding is the preferred context root because the request already binds contract, review material, requirement and Executor formation identity.

## 12. Evidence freshness and revocation semantics

`observed_at` or a self-declared timestamp in a receipt is not proof of freshness.

The canonical Evidence Trust Profile defines what `valid now` means for the selected mechanism.

For the first slice, fail closed unless the Freeze Gate can establish that:

```text
the decision event occurred inside the accepted validity window
AND
required authority evidence is valid under the canonical trust profile at freeze time
```

If the chosen external mechanism exposes revocation/status and the trust profile requires checking it, `UNKNOWN`, unavailable or stale status blocks freeze.

No silent fallback to older cached authority is allowed.

## 13. F-7 — Authority Substitution

```text
correct requirement
+ wrong actor/account/organization/context accepted as equivalent
```

Invariant:

```text
"SOME HUMAN APPROVED" != "THE REQUIRED AUTHORITY APPROVED"
AUTHORITY IDENTITY MUST BIND TO EXACT DECISION CONTEXT
```

## 14. F-8 — Authority Requirement Injection / Downgrade

```text
superior policy requires A
→ lower layer injects weaker B
→ real actor valid for B approves
→ valid evidence for B
→ wrong freeze
```

Invariant:

```text
AUTHORITY REQUIREMENT MUST COME FROM CANONICAL SUPERIOR SOURCES
LOWER TRUST MAY ADD BUT NOT REMOVE SUPERIOR REQUIREMENTS
```

## 15. F-9 — Authority Policy Source Substitution

```text
structurally valid alternate policy/project source S2
is accepted instead of canonical S
```

Canonical source identity binds:

```text
repository + commit + path + content identity + source role + trust layer
```

Valid-looking content from the wrong source is not authority.

## 16. F-10 — Evidence Self-Issuance

Failure:

```text
Executor / Formation / Decision Adapter / Freeze component
creates an authority-like evidence artifact
        ↓
Executor verifies its own artifact
        ↓
freeze
```

Invariant:

> **EXECUTOR CANNOT BE ITS OWN HUMAN-AUTHORITY ROOT.**

An Executor-local component may transform, cache or verify externally rooted evidence according to canonical rules.

It may not be the sole issuer/trust root of the evidence that establishes human authority.

## 17. F-11 — Issuer Substitution / Provider Shopping

Failure:

```text
canonical requirement expects trusted issuer/profile A
        ↓
caller / adapter selects B
or tries providers until one returns YES
        ↓
valid evidence from B
        ↓
freeze
```

Invariant:

```text
ISSUER / TRUST PROFILE SELECTION MUST COME FROM CANONICAL SUPERIOR POLICY
NO RUNTIME PROVIDER SHOPPING
NO PERMISSIVE FALLBACK WHEN THE CANONICAL PROVIDER IS UNAVAILABLE
```

Unavailable required evidence means BLOCK, not select another source.

## 18. F-12 — Evidence Scope Drift

Failure:

```text
real evidence
+ correct actor
+ correct authority class
BUT
wrong project / organization / tenant / decision / request / validity interval
        ↓
freeze
```

Invariant:

```text
AUTHORITY EVIDENCE MUST SATISFY THE EXACT DECISION CONTEXT
CROSS-CONTEXT EVIDENCE IS INVALID EVEN WHEN THE ACTOR AND ROLE ARE REAL
```

## 19. F-13 — Verifier / Trust Profile Substitution

This is distinct from F-11.

F-11 substitutes the issuer/provider.

F-13 keeps a plausible issuer identity but substitutes how that issuer is verified.

Examples:

```text
caller-selected permissive verifier
alternate discovery endpoint
caller-selected key set / trust root
"skip signature" verification mode
issuer string used to dynamically select an untrusted verifier
```

Invariant:

```text
VERIFIER SELECTION AND TRUST ROOTS MUST COME FROM THE CANONICAL TRUST PROFILE
EVIDENCE CONTENT MAY NOT SELECT ITS OWN VERIFIER
CALLER MAY NOT OVERRIDE VERIFICATION SEMANTICS
```

The local verifier implementation is additionally pinned by the exact Executor commit used by formation/freeze.

## 20. F-14 — Evidence Freshness / Revocation Drift

Failure:

```text
actor once had authority
→ evidence was once valid
→ authority expires/revokes or evidence becomes stale
→ old proof is reused at freeze
```

Invariant:

```text
VALID ONCE != VALID FOR CURRENT FREEZE
FRESHNESS / STATUS SEMANTICS COME FROM CANONICAL TRUST PROFILE
UNKNOWN REQUIRED STATUS = BLOCK
```

## 21. Trust and requirement drift after human review

Any change to:

```text
canonical requirement sources
authority_requirement_sha256
canonical evidence trust source
evidence_trust_profile_sha256
review material
draft contract
Executor formation identity
```

invalidates the previous decision for freeze.

Correct transition:

```text
change
→ new canonical hashes
→ new review material / decision request
→ previous receipt stale
→ new human review required
```

## 22. Exact Freeze Gate algorithm — design semantics

Only `ACCEPT` may be freeze-eligible.

Freeze Gate must independently:

```text
1. re-verify exact Executor/project canonical source identities;
2. resolve system + project + valid task authority requirements;
3. compose requirements conjunctively;
4. recompute authority_requirement_sha256;
5. resolve the canonical Evidence Trust Profile from superior sources;
6. recompute evidence_trust_profile_sha256;
7. verify receipt hashes against current review/request/contract state;
8. resolve evidence refs only inside the canonical trust profile;
9. verify external issuer identity using canonical verification semantics;
10. verify Decision Event Evidence;
11. verify Authority Entitlement Evidence;
12. verify actor identity equality across receipt and evidence;
13. verify exact authority/context bindings;
14. verify freshness/status required by the canonical trust profile;
15. verify current draft hash == contract hash to be frozen.
```

Any missing, unknown, stale or mismatched required fact:

```text
AUTHORIZED_AND_FROZEN = FORBIDDEN
```

## 23. Freeze Gate remains a verifier, not IAM

Freeze Gate may know:

```text
canonical source identities
required authority class identifiers
canonical evidence trust profile identity
verification rules
expected exact context bindings
```

It must not own:

```text
users
organization membership
role assignment
standing delegation
provider fallback policy invented at runtime
```

It also may not mint the evidence it accepts as the sole proof of human authority.

## 24. Replay semantics

No global one-time human-decision receipt ledger is introduced.

```text
same receipt + different requirement/trust/request/contract/review context = INVALID
same receipt + same immutable identities + still-valid external evidence = same authorization fact
```

Same-identity revalidation is idempotent verification, not new or broader authority.

Exactly-once consequential side effects remain a separate action-consumption property.

## 25. Required adversarial cases before implementation

At minimum the future boundary must reject:

1. caller-forged Human Decision Receipt;
2. fabricated evidence reference;
3. valid login without required authority;
4. Human A receipt paired with Human B evidence;
5. correct actor in wrong organization/tenant/context;
6. caller/model injects weaker authority requirement;
7. task or formation removes superior requirement;
8. missing requirement source defaults permissively;
9. wrong policy/project repository or commit;
10. copied/dirty/untracked canonical authority file;
11. caller-selected alternative trust profile;
12. receipt-selected issuer/provider;
13. arbitrary evidence URL selects network origin;
14. Executor/Decision Adapter self-issues the sole authority evidence;
15. correct issuer string with attacker-selected permissive verifier;
16. token/evidence selects its own discovery endpoint or trust root;
17. valid authority evidence for wrong decision request;
18. valid authority evidence for wrong project/org/tenant;
19. valid evidence from expired/revoked/stale authority;
20. required status is unavailable/unknown;
21. provider unavailable and runtime falls back to a weaker provider;
22. review/trust profile changes after human decision;
23. wrong authority-requirement or trust-profile hash in receipt;
24. `REJECT` substituted as `ACCEPT`;
25. `MODIFY` executed without a new review cycle;
26. old approval generalized as standing trust;
27. decision adapter claims an action occurred without externally verifiable decision-event evidence;
28. Freeze Gate authors/selects a weaker policy, issuer or verifier.

Expected for every unauthorized or unresolved case:

```text
FAIL CLOSED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 26. Current adversarial-review findings

```text
R-1 Authorization Receipt too strong
 -> Human Decision Receipt

R-2 decision adapter too broad
 -> decision capture separated from authority evidence

R-3 receipt self-described bounded authority
 -> boundedness moved to exact verifier semantics

R-4 F-7 Authority Substitution explicit

R-5 authority requirement separated from authority ownership

R-6 F-8 Authority Requirement Injection / Downgrade explicit

R-7 authority requirement drift bound into decision identity

R-8 formation profile rejected as authority owner

R-9 requirements compose conjunctively

R-10 F-9 Authority Policy Source Substitution explicit

R-11 existing verified project/policy source machinery reused
 -> no second authority policy root

R-12 authority requirement separated from evidence source

R-13 evidence ref reduced to locator only
 -> cannot select provider/verifier/trust root

R-14 decision fact split from proof of decision event
 -> external evidence must collectively prove event + entitlement

R-15 F-10 Evidence Self-Issuance explicit

R-16 F-11 Issuer Substitution / Provider Shopping explicit

R-17 F-12 Evidence Scope Drift explicit

R-18 F-13 Verifier / Trust Profile Substitution explicit

R-19 F-14 Evidence Freshness / Revocation Drift explicit

R-20 trust-profile identity bound into full review/decision/freeze chain
```

F-7 through F-14 must be reconciled into the superior human-authority model before that model is ever merged.

## 27. External Authority Evidence Trust Review — current result

Provisional ownership is now:

```text
EXECUTOR_POLICY / PROJECT GOVERNANCE
  own canonical authority requirement + evidence trust requirements

EXTERNAL AUTHORITY SYSTEM
  owns mutable identity/role/authority truth
  produces externally rooted evidence

HUMAN DECISION ADAPTER
  presents exact material and records a local event
  owns no authority truth and selects no trust provider

HUMAN DECISION RECEIPT
  records exact decision bindings and evidence refs
  is not proof

FREEZE GATE
  resolves canonical trust snapshot
  verifies external decision-event + entitlement claims
  owns neither IAM membership nor the evidence trust policy
```

The design deliberately does not choose OAuth, OIDC, passkeys, GitHub approvals, signatures, PKI, HMAC, a provider API, or a UI.

## 28. Gate

```text
AUTHORITY CONTEXT OWNERSHIP: SUBSTANTIALLY RESOLVED
EXTERNAL AUTHORITY EVIDENCE TRUST: SUBSTANTIALLY RESOLVED AT DESIGN LEVEL
IMPLEMENTATION: BLOCKED
MERGE: NO
```

One design question remains before accepting PR #52:

> What is the minimum canonical Evidence Trust Profile for the first GP001 human-decision slice — specifically which claims must be externally provable, without yet selecting a concrete identity technology or provider?

The answer must be small enough to test adversarially and must not become a generic IAM schema.
