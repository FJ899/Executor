---
document: "Pattern A Technology Evaluation"
version: "0.1"
status: "DRAFT / PROVIDER EVALUATION / NO SELECTION"
date: "2026-08-09"
scope: "real technology evaluation for the external transaction-approval authority domain"
repository: "litrgratis-pixel/Executor"
depends_on:
  - "docs/governance/VERIFIED_HUMAN_AUTHORITY_MODEL.md"
  - "docs/governance/MINIMAL_HUMAN_DECISION_RECEIPT_DESIGN.md"
  - "docs/governance/MINIMAL_VERIFIED_HUMAN_AUTHORITY_CONTRACT.md"
  - "docs/governance/MINIMAL_EXTERNAL_TRUST_BOUNDARY_DESIGN.md"
  - "docs/governance/TRUST_TECHNOLOGY_COMPARISON.md"
  - "docs/governance/TRUST_TECHNOLOGY_COMPARISON_ADVERSARIAL_REVIEW.md"
---

# Pattern A Technology Evaluation v0.1

## 1. Purpose

This document evaluates real technology/product classes only after the trust requirements were fixed.

It does **not** select a provider and does not authorize implementation.

Core rule:

> **THE EVIDENCE REQUIREMENTS SELECT THE TECHNOLOGY. TECHNOLOGY CONVENIENCE MUST NOT WEAKEN THE EVIDENCE REQUIREMENTS.**

The Pattern A target is:

```text
EXTERNAL TRANSACTION-APPROVAL AUTHORITY DOMAIN
  owns externally rooted principal/event truth
  records request-origin event
  presents exact review/decision context
  records direct human ACCEPT
  exposes independently verifiable evidence
        ↓
EXECUTOR
  verifies only
```

The evaluation deliberately asks what each technology **proves**, not whether the vendor generally describes the product as secure.

## 2. Fixed evidence matrix

A first-slice Pattern A implementation requires all of the following properties.

| ID | Requirement | Must prove |
|---|---|---|
| R1 | Request origin event | Externally rooted principal P originated exact governed request event R. |
| R2 | Decision event | The same principal P performed explicit ACCEPT event D. |
| R3 | Exact reviewed content binding | D is bound to the exact review/decision material Q that the human was presented. |
| R4 | Event integrity / durability | Event identity and content/revision cannot silently drift; later verification can reconstruct the relevant event truth. |
| R5 | Direct human action provenance | Provider distinguishes direct principal action from service/automation acting for or as the principal. |
| R6 | External trust root | Identity/event truth is rooted outside the caller-controlled Executor path. |
| R7 | Executor verifier only | Executor consumes and verifies evidence; it does not mint the underlying human-event truth. |
| R8 | No Executor IAM ownership | Executor does not own user/role/identity truth required to make the decision valid. |
| R9 | Same-principal binding | Request origin and decision actor are comparable inside one canonical subject namespace/trust domain. |
| R10 | Freshness / status | Evidence status and freshness required by the canonical trust profile can be checked at freeze. |

Evaluation vocabulary:

```text
PASS
The documented mechanism directly supports the required property in the relevant architecture.

PARTIAL
Useful evidence exists, but another independently trusted mechanism or strict design constraint is needed.

FAIL
The documented mechanism does not establish the property for the first slice.

CONFIG-DEPENDENT
The product can support the property, but a concrete configuration must be proven adversarially.
```

No numeric score is used. A critical FAIL means the product is not a complete Pattern A boundary as evaluated.

## 3. Candidates evaluated

Four real candidates were selected because they represent materially different ways to implement a transaction-approval domain:

1. **PingAM transactional authorization** — identity/policy server with transaction-specific authorization.
2. **Microsoft Teams / Power Automate Approvals + Dataverse/Purview audit** — enterprise human approval workflow domain.
3. **Docusign eSignature** — externally hosted reviewed-document/signing transaction with tamper-evident completion evidence.
4. **OneSpan Mobile Authenticator Studio transaction data signing** — external/mobile transaction review + cryptographic approval ceremony.

These are evaluation targets, not endorsements.

## 4. Candidate A — PingAM transactional authorization

### Documented properties

PingAM transactional authorization creates a transaction token (`TxId`) in its Core Token Service. The token includes policy-evaluation information such as realm, resource, subject, audit tracking ID and authentication method. PingAM verifies that those details do not change during the transaction. The user completes a configured authorization/authentication tree; the transaction reaches `COMPLETED`, is accepted for one access, and is then marked for deletion so it cannot grant repeated access.

PingAM can present transaction-specific text in the authorization tree, including push-based Yes/No approval examples. PingAM audit logs contain unique event IDs, timestamps, transaction IDs and authenticated user IDs, and can correlate activity across the request boundary.

### Matrix

| Requirement | Result | Finding |
|---|---|---|
| R1 Request origin event | PARTIAL | AM can log an authenticated external access request and transaction ID, but its standard transactional-authorization model does not by itself prove the original natural-language Executor request event or its exact payload identity. Intake would need to be deliberately routed through or independently bound to this trust domain. |
| R2 Decision event | PASS | TxId/state and the transactional authorization flow provide a concrete transaction completion event. |
| R3 Exact reviewed content binding | PARTIAL | The tree can display transaction context and AM protects stored transaction details from drift, but the docs do not establish a generic immutable `decision_request_sha256` plus proof of the exact rendered Executor review surface. |
| R4 Event integrity/durability | PARTIAL | Structured audit records exist, but normal audit storage is an operational logging subsystem; tamper-evident long-term evidence is deployment-dependent rather than inherent to transactional authorization. |
| R5 Direct human action provenance | CONFIG-DEPENDENT | Push/Yes-No or explicit authentication trees can require human action, but Ping policy also supports paths such as automatic approval in adjacent products/configurations. The canonical tree/policy must forbid non-human success paths. |
| R6 External trust root | PASS | A separately governed PingAM domain can own subject/authentication truth. |
| R7 Executor verifier only | PASS | Executor can consume PingAM transaction/audit evidence rather than own it. |
| R8 No Executor IAM ownership | PASS | Identity and policy can remain in PingAM. |
| R9 Same-principal binding | PASS | AM audit/authentication data uses a stable authenticated user identity within realm/trust context. |
| R10 Freshness/status | PASS | Transaction state and single-use semantics provide explicit current transaction status. |

### Verdict

```text
STRONG PARTIAL CANDIDATE
NOT A COMPLETE FIRST-SLICE BOUNDARY AS DOCUMENTED
```

Main blockers:

```text
request-origin event is not automatically the governed Executor request
exact Executor review-surface commitment is not proven out of the box
audit tamper-evidence/durability needs an explicit trust design
```

A future spike is justified only if these three gaps can be solved without moving identity/event ownership back into Executor.

## 5. Candidate B — Microsoft Teams / Power Automate Approvals + Dataverse/Purview

### Documented properties

Microsoft Teams/Power Automate allows a signed-in user to create an approval request, enter approval details and choose approvers. Assigned users can view the request and explicitly approve or reject it from Teams, Power Automate, email or the approvals center.

Approvals are stored in Dataverse. Microsoft documents Purview audit events including `Created new approval request`, `Viewed approval request details`, `Approved approval request` and `Rejected approval request`. Dataverse auditing can record who created or updated a record, which fields changed, old/new values, timestamps and user IDs; audit data is retrievable through APIs.

However, Microsoft also documents that audit retention is configurable and privileged administrators can delete audit history. Approval requests can also be created by automated flows rather than only through direct human interaction.

### Matrix

| Requirement | Result | Finding |
|---|---|---|
| R1 Request origin event | CONFIG-DEPENDENT | A directly created Teams approval plus Purview `Created new approval request` is a plausible external origin event. But Power Automate flows can also create approvals, so the trust profile must distinguish/forbid automation-created origin events for this slice. |
| R2 Decision event | PASS | Explicit approve/reject responses are first-class platform events and responses are persisted. |
| R3 Exact reviewed content binding | PARTIAL | Approval title/details are displayed and Dataverse can audit changes, but the platform documentation does not establish a cryptographic/tamper-evident commitment tying the human response to an exact immutable Executor decision-request representation. |
| R4 Event integrity/durability | PARTIAL | Dataverse/Purview offer strong auditability and before/after change history, but Dataverse audit retention is configurable and privileged deletion is supported. This is not an immutable evidence root by default. |
| R5 Direct human action provenance | CONFIG-DEPENDENT | Interactive responses are user actions, but the complete API/automation surface must be adversarially checked to prove that service automation cannot create a response indistinguishable from a human response. |
| R6 External trust root | PASS | Microsoft tenant/Entra/Dataverse is external to Executor. |
| R7 Executor verifier only | PASS | Executor can read approval and audit evidence. |
| R8 No Executor IAM ownership | PASS | Microsoft owns tenant user identity. |
| R9 Same-principal binding | PASS | User identity is tenant-rooted if request creation and approval both occur in the same tenant/domain. |
| R10 Freshness/status | PASS | Approval state is explicit; audit timestamps/history are available. |

### Verdict

```text
PROMISING WORKFLOW DOMAIN
NOT YET A TRUST-COMPLETE PATTERN A BOUNDARY
```

Main blockers:

```text
exact reviewed-content commitment is weaker than required
immutable evidence is not guaranteed by default
human-vs-automation provenance requires concrete API/configuration proof
```

This candidate is attractive because it can externalize both request creation and approval, but doing so would move the first product intake surface into a Microsoft approval domain. That UX/product tradeoff must be explicit rather than hidden.

## 6. Candidate C — Docusign eSignature

### Documented properties

Docusign tracks transaction actions such as sending, viewing, signing and declining. Completed transactions produce a Certificate of Completion and tamper-evident signed documents. Docusign states that transaction data forms a neutral third-party audit trail and is retained to support later transaction validation. It also supports multiple signer identity-verification methods, from basic methods to stronger identity checks.

The signer is presented the document in the Docusign signing ceremony and the final signed document is sealed against undetected modification. This is a strong fit for the **reviewed content + direct signing event** half of the problem.

### Matrix

| Requirement | Result | Finding |
|---|---|---|
| R1 Request origin event | PARTIAL | Docusign can record the sender/envelope creation transaction, but an Executor request is not automatically the Docusign envelope-origin event. APIs can create envelopes; proving that the same human directly originated the governed request requires a constrained external intake design. |
| R2 Decision event | PASS | Signing/declining is a first-class transaction event. |
| R3 Exact reviewed content binding | PASS | The human signing ceremony presents the document, the signed document is tamper-sealed, and completion evidence binds the signing process to the completed document. |
| R4 Event integrity/durability | PASS | Docusign provides a Certificate of Completion, audit trail and tamper-evident document; Docusign states transaction data is retained for validation even after subscription termination. |
| R5 Direct human action provenance | CONFIG-DEPENDENT | The signing ceremony is directly user-facing, but signer authentication strength varies and embedded/API flows require careful proof that application/service activity cannot be mistaken for the signer’s action. |
| R6 External trust root | PASS | Docusign is an external transaction/evidence domain. |
| R7 Executor verifier only | PASS | Executor can consume signed document/completion evidence. |
| R8 No Executor IAM ownership | PASS | Signer identity verification can be rooted in Docusign/external identity methods. |
| R9 Same-principal binding | CONFIG-DEPENDENT | The request-origin sender and signer identities can be compared only if both are externally bound in the intended workflow. |
| R10 Freshness/status | PASS | Envelope/completion status and timestamps are recorded. |

### Verdict

```text
STRONGEST REVIEW-CONTENT / DURABLE-EVIDENCE CANDIDATE
BUT REQUEST-ORIGIN MODEL DOES NOT NATURALLY MATCH EXECUTOR INTAKE
```

Main blocker:

```text
FACT A — same externally verified principal originated the governed Executor request
```

Docusign is therefore closer to a complete trusted **decision ceremony** than a natural end-to-end request-intent authority domain for the current product UX. It may also be operationally too heavy for the first developer-oriented slice.

## 7. Candidate D — OneSpan Mobile Authenticator Studio transaction data signing

### Documented properties

OneSpan transaction data signing stores pending transaction data on a server, presents the transaction fields to the user in Mobile Authenticator Studio, requires the user to tap Approve and confirm identity using OTP or biometrics, then generates an e-signature over the selected transaction fields and sends it to a server for validation.

OneSpan also documents push-and-sign and app-to-app flows where a third-party application initiates the approval, the OneSpan app displays request details, the human approves, and the app produces a signature/approval response.

### Matrix

| Requirement | Result | Finding |
|---|---|---|
| R1 Request origin event | FAIL AS COMPLETE PATTERN A | OneSpan explicitly describes the transaction as starting outside the authenticator app, with data stored on an integrator/server. That upstream event can remain Executor/integrator-controlled and therefore is not automatically an externally rooted request-origin fact. |
| R2 Decision event | PASS | A concrete pending transaction is selected and approved/signed. |
| R3 Exact reviewed content binding | PASS | The user is shown transaction fields and those fields feed the cryptographic signing operation. This directly addresses review/signing surface substitution better than a generic login. |
| R4 Event integrity/durability | PARTIAL | The generated signature protects transaction content, but durable independent event/evidence retention depends on the surrounding server/integration; the Mobile Authenticator Studio flow alone is not the full evidence archive. |
| R5 Direct human action provenance | PASS | The documented flow requires the user to open/select the transaction, tap Approve and confirm using OTP/biometrics. |
| R6 External trust root | PARTIAL | The authenticator/device credential is external to Executor, but transaction data and validation services remain integration-owned. |
| R7 Executor verifier only | PARTIAL | A design can keep Executor as verifier, but the normal architecture expects an integrator backend to host pending data and validate signatures. |
| R8 No Executor IAM ownership | PASS/PARTIAL | Device/account identity can live in OneSpan, but deployment details determine how user accounts are mapped. |
| R9 Same-principal binding | CONFIG-DEPENDENT | Requires the request-origin identity to be externally established in the same subject domain; the documented transaction-signing flow alone does not provide that. |
| R10 Freshness/status | PASS | Pending transaction state plus explicit signing workflow provides current transaction status. |

### Verdict

```text
EXCELLENT EXACT-DECISION CEREMONY COMPONENT
NOT A COMPLETE PATTERN A DOMAIN
```

OneSpan strongly addresses F-23 and much of F-21, but FACT A remains outside the external transaction-signing domain. It is therefore closer to a strong Pattern B component unless paired with a separately externally rooted request-intake mechanism.

## 8. Cross-candidate matrix

| Requirement | PingAM | Microsoft Approvals | Docusign | OneSpan MAS |
|---|---|---|---|---|
| R1 Request origin event | PARTIAL | CONFIG-DEPENDENT | PARTIAL | FAIL |
| R2 Decision event | PASS | PASS | PASS | PASS |
| R3 Exact reviewed content | PARTIAL | PARTIAL | PASS | PASS |
| R4 Durable/tamper-evident event | PARTIAL | PARTIAL | PASS | PARTIAL |
| R5 Direct human action | CONFIG-DEPENDENT | CONFIG-DEPENDENT | CONFIG-DEPENDENT | PASS |
| R6 External trust root | PASS | PASS | PASS | PARTIAL |
| R7 Executor verifier only | PASS | PASS | PASS | PARTIAL |
| R8 No Executor IAM | PASS | PASS | PASS | PASS/PARTIAL |
| R9 Same-principal binding | PASS if intake externalized | PASS in same tenant | CONFIG-DEPENDENT | CONFIG-DEPENDENT |
| R10 Freshness/status | PASS | PASS | PASS | PASS |
| Complete first-slice Pattern A today | NO | NO | NO | NO |

## 9. Main finding — request origin is the hard missing half

All four systems can produce useful evidence around an approval/signing decision.

None automatically proves the current Executor product’s first fact:

```text
externally verified principal P
originated exact governed request event R
```

unless request intake itself is moved into or deliberately bound at the external trust domain **at creation time**.

Therefore:

> **APPROVAL PLATFORM != COMPLETE REQUEST-INTENT AUTHORITY DOMAIN.**

And:

```text
EXTERNAL APPROVAL EVIDENCE
        +
RETROACTIVE REQUEST-ORIGIN ATTRIBUTION
        =
REJECT
```

This is F-22 in concrete technology form.

## 10. Product consequence

Pattern A has a real product/UX cost.

To satisfy FACT A without inventing origin after the fact, the system likely needs one of these shapes:

### Shape A1 — Externalized governed request intake

```text
HUMAN
  creates exact request in external trust domain
        ↓
external request event R
        ↓
Executor imports/verifies R
        ↓
formation
        ↓
external domain presents exact Q
        ↓
HUMAN ACCEPT event D
```

Strongest evidence model, but changes the current natural-language front door.

### Shape A2 — External origin attestation at intake

```text
HUMAN submits request to Executor
        +
external trust mechanism contemporaneously binds P to exact request hash H
        ↓
formation
        ↓
external approval of exact Q by same P
```

This preserves more of the Executor UX but requires a concrete external origin-attestation mechanism. That begins to resemble a composed Pattern A/B design rather than a single approval platform.

## 11. Research ordering after real-product evaluation

No provider is selected.

The next research priority should be:

```text
1. Microsoft Approvals / Dataverse / Purview
   only as a full externalized intake+approval experiment
   because it can natively hold both creation and response events in one tenant.

2. PingAM transactional authorization
   as a transaction-policy experiment
   to test whether exact Q + immutable audit evidence can be made canonical
   without putting request truth back in Executor.

3. Docusign
   as a high-assurance reviewed-content/evidence benchmark,
   not as the default product UX.

4. OneSpan MAS
   as a decision-ceremony benchmark/component,
   not as a complete Pattern A domain.
```

This is **research ordering**, not provider selection.

## 12. Rejection criteria for the next spike

A concrete candidate must be rejected immediately if:

```text
request-origin fact is created only after later login/approval;
request details can mutate without a verifiable historical revision;
approval can be produced by service automation indistinguishably from a human;
review surface is not bound to the exact approved identity;
audit/evidence can disappear without a superior durability policy;
provider selection can be changed by caller input;
Executor must own the identity database to make the proof work;
REQUEST_INTENT success can be promoted to WRITE/MERGE/DEPLOY authority.
```

## 13. Sources checked

Checked on 2026-08-09. Only vendor/standards primary documentation was used for product-property claims.

### Ping Identity / PingAM

- `Transactional authorization | PingAM` — https://docs.pingidentity.com/pingam/8/am-authorization/transactional-authorization.html
- `Transactional authorization | PingAM 7.2` — https://docs.pingidentity.com/pingam/7.2/authorization-guide/transactional-authorization.html
- `Audit logging reference | PingAM` — https://docs.pingidentity.com/pingam/8/security/sec-maint-audit-ref.html
- `Audit logging | PingAM` — https://docs.pingidentity.com/pingam/8/security/audit-logging.html

### Microsoft

- `Get started with Power Automate approvals` — https://learn.microsoft.com/en-us/power-automate/get-started-approvals
- `Manage the Approvals app in Microsoft Teams` — https://learn.microsoft.com/en-us/microsoftteams/approval-admin
- `Manage Dataverse auditing` — https://learn.microsoft.com/en-us/power-platform/admin/manage-dataverse-auditing
- `Retrieve the history of audited data changes` — https://learn.microsoft.com/en-us/power-apps/developer/data-platform/auditing/retrieve-audit-data

### Docusign

- `How Docusign uses transaction data and the Certificate of Completion` — https://www.docusign.com/trust/security/transaction-data-use
- `Platform safety` — https://www.docusign.com/safety/platform-safety
- `eSignature Detailed Features` — https://www.docusign.com/en-gb/products/electronic-signature/features
- `Embedded signing` — https://developers.docusign.com/docs/esign-rest-api/esign101/concepts/embedding/embedded-signing/

### OneSpan

- `Transaction Data Signing` — https://docs.onespan.com/mobile/docs/mas-features-transaction-data-signing
- `Manual Transaction Data Signing` — https://docs.onespan.com/mobile/docs/mas-5-pg-manual-txn-signing-5-6-0
- `Push Notification / Push and Sign` — https://docs.onespan.com/mobile/docs/mas-5-pg-push-notification-5-5-0
- `App-to-app signing` — https://docs.onespan.com/mobile/docs/mas-5-pg-app-to-app-signing-mas-5-6-0

## 14. Current gate

```text
PR #51: DIRECTION ACCEPTED / UNMERGED
PR #52: DIRECTION ACCEPTED / UNMERGED
PR #53: DIRECTION ACCEPTED / UNMERGED
PR #54: DIRECTION ACCEPTED / UNMERGED
PR #55: DIRECTION ACCEPTED / UNMERGED
PATTERN A TECHNOLOGY EVALUATION: UNDER REVIEW
PROVIDER: NOT SELECTED
IMPLEMENTATION: NOT STARTED
MERGE: NO
```

The next decision is not "which vendor do we buy?"

It is:

> **Do we accept the finding that a complete Pattern A solution requires request-origin evidence at intake time, and therefore must explicitly choose between externalized intake or an external origin-attestation mechanism before any provider can qualify?**
