---
document: "Minimal External Trust Boundary Design"
version: "0.2"
status: "DRAFT / ADVERSARIAL TECHNOLOGY-AGNOSTIC DESIGN / IMPLEMENTATION BLOCKED"
date: "2026-08-09"
scope: "minimum external trust facts required to establish REQUEST_INTENT human authority for REQUEST_TO_CONTRACT_001"
repository: "litrgratis-pixel/Executor"
depends_on:
  - "docs/governance/VERIFIED_HUMAN_AUTHORITY_MODEL.md"
  - "docs/governance/MINIMAL_HUMAN_DECISION_RECEIPT_DESIGN.md"
  - "docs/governance/MINIMAL_VERIFIED_HUMAN_AUTHORITY_CONTRACT.md"
---

# Minimal External Trust Boundary Design v0.2

## 1. Purpose

This document defines the smallest external trust boundary that could later support the first verified-human-authority implementation slice.

It deliberately does **not** select:

- OAuth or OIDC;
- GitHub approvals;
- passkeys;
- signatures, PKI or HMAC;
- a specific identity provider;
- a UI;
- an IAM database;
- an organization model;
- a ledger.

The design answers only:

> What externally rooted facts must exist before Executor may conclude that the same verified principal who originated one exact request explicitly ACCEPTED one exact decision request for one exact reviewed draft?

The authority dimension is intentionally narrow:

```text
REQUEST_INTENT ONLY
```

Therefore:

```text
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

A positive result here must grant no WRITE, MERGE, DEPLOY, NETWORK, SECRET or other downstream action authority.

## 2. Core trust rule

Executor may verify authority facts.

Executor must not own the mutable identity truth that makes those facts authoritative.

Core invariant:

> **EXECUTOR VERIFIES AUTHORITY != EXECUTOR OWNS IDENTITY AUTHORITY.**

The trusted chain is:

```text
CANONICAL SUPERIOR GOVERNANCE
    selects the accepted trust profile
        ↓
EXTERNAL TRUST MECHANISM
    owns identity / event truth
        ↓
EXTERNALLY VERIFIABLE FACTS
        ↓
EXECUTOR TRUST VERIFIER
    checks facts under the canonical profile
        ↓
VERIFIED REQUEST_INTENT AUTHORITY FACT
```

Executor may contain verification code.

That does not make Executor the issuer or root of the human identity/event truth being verified.

## 3. What “external” means

For this design, `external` does not merely mean:

```text
another Python class
another module
another process
another local JSON file
```

The trust root must be outside the caller-controlled Executor formation/verification path.

The external mechanism must provide evidence whose credibility does not originate from:

```text
caller assertions
model output
formation state labels
Human Decision Receipt fields
Executor-generated role labels
Executor-generated subject identities
Executor-generated "verified" result JSON
```

An Executor-local component may retrieve, normalize, cache or verify externally rooted evidence.

It may not become the sole source of the identity/event fact that it later verifies.

The Executor/service identity used for verification must also not possess a capability that can silently manufacture a human-origin or human-ACCEPT event that the same verifier would later treat as direct human action.

## 4. First-slice minimal facts

The first slice requires three externally rooted facts plus exact identity/context binding.

### FACT A — Request Origin Event

The trust mechanism must establish that one verified principal directly originated the governed request event.

Minimum semantics:

```text
trust_domain_id
issuer_identity
subject_namespace
subject_id
request_event_id
request_event_type
request_event_payload_commitment / immutable revision identity
canonical governed user-request identity / digest
human-action provenance required by the trust profile
occurred_at or equivalent event ordering/freshness fact
status/validity required by the trust profile
```

Conceptual meaning:

```text
principal P
personally originated request event R
whose committed payload/revision is E
whose exact governed request identity is H
inside trust domain T
```

The statement:

```text
originator = USER
```

is not evidence.

A stable event ID without a stable payload/revision commitment is not sufficient.

### FACT B — Decision Event

The trust mechanism must establish that one verified principal directly made the bounded decision for the exact formation decision request.

Minimum semantics:

```text
trust_domain_id
issuer_identity
subject_namespace
subject_id
decision_event_id
decision_event_payload_commitment / immutable revision identity
decision = ACCEPT
exact decision_request_sha256 or equivalent immutable binding
human-action provenance required by the trust profile
occurred_at or equivalent event ordering/freshness fact
status/validity required by the trust profile
```

Conceptual meaning:

```text
principal P
personally performed ACCEPT event D
whose committed payload/revision is E2
for exact decision request Q
inside trust domain T
```

A generic event such as:

```text
button_clicked = true
```

is insufficient unless the external mechanism binds that event to the exact decision request identity and proves the required principal-action provenance.

### FACT C — Same Principal Binding

For the first slice:

```text
REQUEST ORIGINATOR PRINCIPAL
        ==
DECISION ACTOR PRINCIPAL
```

But principal equality is not bare string equality.

The comparison must use a canonical subject binding such as the semantic tuple:

```text
trust_domain_id
issuer_identity
subject_namespace
subject_id
```

Therefore:

```text
SUBJECT STRING EQUALITY != VERIFIED IDENTITY EQUALITY
```

The first slice deliberately requires both facts to be comparable inside one canonical trust domain / identity namespace.

Cross-provider account linking and federation are out of scope.

## 5. Event identity and event content are different bindings

A provider-local event ID may remain stable while the record displayed or returned for that event changes.

Therefore:

```text
EVENT IDENTITY != EVENT CONTENT IDENTITY
```

The trust mechanism must let Executor verify the event payload/revision that existed for the authoritative event being relied upon.

Acceptable technology-agnostic properties include any mechanism that establishes an immutable or tamper-evident commitment to the event contents relevant to authority, for example:

```text
immutable event record
version/revision identity
provider-authenticated payload digest
tamper-evident audit entry
another independently verifiable event-content commitment
```

The design does not choose which.

A verifier must never silently reinterpret the current mutable representation of event `R` as proof of the original authority event if the original bound content cannot be established.

## 6. Exact decision context binding

The external mechanism does not need to understand the full Executor contract.

It must, however, bind the human decision event to an immutable decision-request identity.

The Executor decision request must itself bind, directly or through canonical reconstruction, to:

```text
verbatim user request identity
request_id
review_material_sha256
draft_sha256
formation_profile_sha256
canonical_task_sha256
executor_commit
authority_requirement_sha256
evidence_trust_profile_sha256
allowed decision set
```

Therefore the external trust mechanism may prove:

```text
P ACCEPTED decision_request_sha256 = Q
```

while Executor independently verifies that `Q` is the exact current decision request for the exact reviewed draft.

This keeps responsibility separated:

```text
EXTERNAL TRUST MECHANISM
    proves WHO acted + WHICH authoritative event/revision + WHICH exact Q

EXECUTOR
    proves WHAT Q means inside the canonical formation state
```

## 7. Human-action provenance is a required external fact

An external provider may support service accounts, delegated applications, automation or on-behalf-of actions.

A provider-issued event is therefore not automatically proof that the human principal directly caused that event.

For the first slice, the canonical trust profile must require an externally verifiable event provenance class equivalent in meaning to:

```text
DIRECT VERIFIED PRINCIPAL ACTION
```

The exact technology-specific label is intentionally not frozen.

The required property is:

> Executor/service credentials cannot manufacture an event that the verifier will accept as a direct request-origin or direct human `ACCEPT` action for the principal whose authority is being proved.

If the provider cannot distinguish direct principal action from service/delegated/automated action with sufficient assurance:

```text
BLOCK
```

## 8. Canonical trust profile owns trust selection

The external mechanism is not selected by evidence content or caller input.

The canonical Evidence Trust Profile must determine at least:

```text
trust_profile_id
accepted trust_domain_id
accepted issuer identity / namespace
verification_profile_id
required claim classes
required event/context bindings
required human-action provenance class
required event payload/revision commitment semantics
freshness / status requirements
canonical source bindings
executor_commit
```

The profile itself comes from verified superior governance under the existing Executor trust hierarchy.

Public runtime APIs must not allow caller-selected overrides such as:

```text
issuer=
trust_domain=
verifier=
verification_endpoint=
keyset_url=
trust_root=
```

Core invariant:

```text
EVIDENCE REF != TRUST SELECTOR
```

## 9. Technology-agnostic capability contract

A future concrete external trust mechanism is acceptable for the first slice only if it can provide or support independent verification of all of the following properties.

### 9.1 Stable trust-domain identity

The verifier can establish which canonical trust domain / issuer namespace produced the evidence.

### 9.2 Stable subject binding

The verifier can establish the principal identity inside that canonical namespace.

### 9.3 Immutable or unambiguous event identity

Request creation and decision actions have event identities that cannot be silently rebound to another event during verification.

### 9.4 Immutable or verifiable event-content commitment

The verifier can establish which exact event payload/revision is being relied upon, rather than trusting only the provider's current mutable rendering of an old event ID.

### 9.5 Exact payload/context binding

The request-origin evidence binds to the exact governed request identity.

The decision evidence binds to the exact decision-request identity.

### 9.6 Direct-principal action provenance

The verifier can distinguish the required direct human action from service/delegated/automated actions that must not satisfy `REQUEST_INTENT_OWNER` in this slice.

### 9.7 Independent evidence integrity

The evidence can be validated without trusting a caller-generated claim that says it is valid.

The technology may achieve this through a signed assertion, trusted API lookup, tamper-evident audit record, authenticated external transaction or another mechanism.

The design does not select which.

### 9.8 Freshness / validity semantics

The verifier can determine whether the required evidence is still valid for the current freeze attempt under the canonical trust profile.

### 9.9 No runtime provider shopping

If the canonical trust mechanism is unavailable or returns an unresolved result:

```text
BLOCK
```

not:

```text
try another provider until one says YES
```

## 10. Evidence references remain locators only

A Human Decision Receipt or formation artifact may contain references to external evidence.

Those references may identify:

```text
event ID
record ID
assertion ID
provider-local evidence locator
```

But they may not decide:

```text
which trust domain is accepted
which verifier runs
which endpoint is trusted
which trust root is valid
which subject namespace is authoritative
which human-action provenance is acceptable
```

If a future mechanism retrieves evidence remotely, arbitrary caller-controlled URLs are not acceptable trust selection.

The canonical trust profile must constrain the retrieval and verification origin.

## 11. Decision Event Evidence and Request Origin Evidence remain distinct claims

The same external system may prove both claims.

The same external artifact may even carry both claims.

But the verifier must keep their meanings separate:

```text
REQUEST ORIGIN CLAIM
  principal P directly originated request R with exact committed event content

DECISION EVENT CLAIM
  principal P directly performed ACCEPT for decision request Q with exact committed event content
```

A valid decision event does not imply request ownership.

A valid request-origin event does not imply later ACCEPT.

Only their verified conjunction plus exact identity/context binding can satisfy the first-slice authority requirement.

## 12. Responsibility split

### Superior Executor governance owns

```text
which authority class is required
which trust profile is canonical
which evidence claim classes are required
which human-action provenance class is required
which verification semantics are acceptable
```

### External trust mechanism owns

```text
mutable identity truth
request-origin event truth
decision-event truth
authoritative event/revision history or equivalent content commitment
provider-side action provenance truth
provider-side validity/status truth
```

### Executor trust verifier owns

```text
canonical trust-profile resolution
external evidence verification
subject-binding comparison
event/revision commitment comparison
exact decision/request identity comparison
fail-closed result
```

### Freeze Gate owns

```text
rechecking exact current formation/contract identities
accepting only a trusted verified-authority fact
creating the later AUTHORIZED_AND_FROZEN transition
```

None of these components may silently absorb the responsibilities of all the others.

## 13. F-19 — Trust Boundary Collapse

Failure:

```text
external evidence exists
        ↓
Executor starts defining identity truth / role truth / issuer trust dynamically
        ↓
Executor verification rules become the effective identity authority
        ↓
Executor verifies authority that Executor itself invented
        ↓
freeze
```

Examples:

```text
Executor creates its own subject IDs and treats them as externally authoritative
Executor decides at runtime which issuer is "trusted"
Executor creates organization membership or role assignments to satisfy its verifier
Executor silently maps unrelated identities together
Executor converts a local session label into external authority truth
```

Invariant:

> **EXECUTOR VERIFIES AUTHORITY != EXECUTOR OWNS IDENTITY AUTHORITY.**

Required behavior:

```text
identity / event truth must remain externally rooted
trust selection must remain canonically governed
Executor may verify but may not self-create the human-authority root
```

## 14. F-20 — Event Payload Rebinding / Mutable Event Drift

Failure:

```text
real external event R exists
        ↓
R originally bound to payload A
        ↓
provider record / editable object / lookup view changes to B
        ↓
R keeps the same event/reference identity
        ↓
verifier reads current B and treats it as historical authority for R
        ↓
wrong request or decision context accepted
```

Invariant:

```text
EVENT IDENTITY != EVENT CONTENT IDENTITY
AUTHORITY EVIDENCE MUST BIND THE AUTHORITATIVE EVENT PAYLOAD / REVISION
```

Expected behavior:

```text
missing immutable/tamper-evident event-content commitment = BLOCK
```

## 15. F-21 — Service-Induced Human Event / Action-Provenance Confusion

Failure:

```text
canonical external provider is real
subject identity is real
provider event is real
        ↓
Executor/service credential can create or trigger event on behalf of subject
        ↓
event is labelled/treated as human-origin or human-ACCEPT
        ↓
verifier accepts it as direct principal action
        ↓
freeze without the human having performed the decision
```

Invariant:

```text
PROVIDER-VALID EVENT != DIRECT HUMAN ACTION
SERVICE ACTION FOR SUBJECT != SUBJECT ACTION
```

Required behavior:

```text
canonical trust profile must require verifiable human-action provenance
Executor/service identity must not be able to manufacture that provenance
ambiguous provenance = BLOCK
```

## 16. Relationship to F-10 through F-21

F-19 through F-21 do not replace the earlier failure modes.

They harden the root and event semantics of the external boundary.

```text
F-10  evidence self-issuance
F-11  issuer/provider substitution
F-12  evidence scope drift
F-13  verifier/trust-profile substitution
F-14  freshness/revocation drift
F-15  intent authority confused with action authority
F-16  verified-result self-minting
F-17  formation-state/request forgery
F-18  cross-issuer subject false equivalence
F-19  trust boundary collapse
F-20  event payload rebinding / mutable event drift
F-21  service-induced human event / action-provenance confusion
```

## 17. Mandatory adversarial questions before technology selection

A concrete mechanism must be rejected if any answer below is unresolved.

1. Can caller/model choose the issuer or verifier?
2. Can Executor mint the sole evidence that it later verifies?
3. Can the external system prove only identity but not exact request/decision event binding?
4. Can two different principals collide because only bare `subject_id` is compared?
5. Can the same event reference be rebound to another payload or revision?
6. Can an event record be edited while retaining the same authority reference?
7. Can evidence for another request or decision be replayed here?
8. Can a stale or revoked identity/event assertion still pass?
9. Can provider unavailability trigger permissive fallback?
10. Can a local session label be treated as external identity authority?
11. Can the verifier silently create or reinterpret organization/role semantics?
12. Can decision evidence prove `ACCEPT` without binding exact `decision_request_sha256`?
13. Can request-origin evidence bind only request text but not the actual request event/revision?
14. Can a caller-created positive verification result be accepted by Freeze Gate?
15. Can formation-state JSON be accepted as proof of current formation state?
16. Can a successful REQUEST_INTENT verification be reused as WRITE/MERGE/DEPLOY authority?
17. Can Executor/service credentials create an event that is accepted as direct human request origin?
18. Can Executor/service credentials create an event that is accepted as direct human `ACCEPT`?
19. Can provider metadata distinguish direct principal action from delegated/service/automated action?
20. Does the verifier fail closed when action provenance is unknown?

Expected whenever any required fact is absent, ambiguous, stale or mismatched:

```text
BLOCKED
NO VERIFIED HUMAN AUTHORITY FACT
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## 18. First-slice non-goals

The design deliberately excludes:

- organization hierarchy;
- RBAC / ABAC;
- repository-owner discovery;
- production approvers;
- enterprise IAM;
- delegation;
- quorum;
- multi-party approval;
- approval chains;
- cross-provider account federation;
- account-linking graph;
- provider marketplace or fallback;
- generic authorization tokens;
- one-time global receipt ledger;
- downstream resource/action authorization.

## 19. Technology selection gate

A concrete technology may be considered only after this design is adversarially accepted.

The chosen mechanism must demonstrate the smallest useful fact set:

```text
FACT 1
externally verified principal P directly originated exact request event R
with verifiable authoritative event-content/revision binding

FACT 2
same externally verified principal P directly performed ACCEPT event D
for exact decision request Q
with verifiable authoritative event-content/revision binding

FACT 3
R and D are verified inside one canonical trust domain / subject namespace
and satisfy the canonical direct-principal action provenance requirement

FACT 4
Q is independently bound by Executor to the exact current review + draft identity
```

The technology is an implementation detail beneath those properties.

The acceptance question is not:

> "Can users log in?"

It is:

> **Can Executor independently establish, without owning the identity authority or being able to manufacture the trusted human events itself, that the same externally verified principal directly originated one exact governed request and directly ACCEPTED the one exact decision request bound to the current reviewed draft?**

Until that property is demonstrable:

```text
IMPLEMENTATION = BLOCKED
AUTHORIZED_AND_FROZEN = FORBIDDEN
```
