---
document: "Trust Technology Comparison Against Fixed Requirements"
version: "0.1"
status: "DRAFT / TECHNOLOGY COMPARISON / NO SELECTION"
date: "2026-08-09"
scope: "comparison of technology classes against the accepted REQUEST_INTENT external trust requirements"
repository: "litrgratis-pixel/Executor"
depends_on:
  - "docs/governance/VERIFIED_HUMAN_AUTHORITY_MODEL.md"
  - "docs/governance/MINIMAL_HUMAN_DECISION_RECEIPT_DESIGN.md"
  - "docs/governance/MINIMAL_VERIFIED_HUMAN_AUTHORITY_CONTRACT.md"
  - "docs/governance/MINIMAL_EXTERNAL_TRUST_BOUNDARY_DESIGN.md"
---

# Trust Technology Comparison Against Fixed Requirements v0.1

## 1. Purpose

This document compares technology classes only after the trust requirements have been fixed.

It does **not** select a provider or authorize implementation.

The selection rule is:

> **THE TRUST CONTRACT MUST SELECT THE TECHNOLOGY. THE TECHNOLOGY MUST NOT REDEFINE THE TRUST CONTRACT.**

Convenience is not evidence.

```text
PROVIDER FEATURE SET
        !=
TRUST REQUIREMENT
```

If a mechanism cannot prove a required fact, Executor must not weaken the fact until the mechanism appears sufficient.

This prevents **Convenience Trust**:

```text
"provider exposes user_id"
      -> redefine user_id as human authority
      -> implementation looks complete
      -> trust property was silently weakened
```

Rejected.

## 2. Fixed first-slice requirement

The first slice concerns only `REQUEST_INTENT` authority.

It must establish:

```text
FACT A
externally verified principal P originated exact request event R

FACT B
same externally verified principal P directly performed ACCEPT event D
for exact decision request Q

FACT C
R and D are comparable inside one canonical trust domain / subject namespace

FACT D
Executor independently proves that Q binds the exact current review material + draft
```

A successful mechanism grants no downstream resource/action authority.

```text
INTENT AUTHORITY != RESOURCE / ACTION AUTHORITY
```

## 3. Fixed trust requirements

### T1 — Canonical trust-domain identity

Must establish which external trust domain / issuer is authoritative.

The caller may not choose it at runtime.

### T2 — Canonical subject binding

Must identify the principal inside the canonical trust domain using more than a bare local string.

Minimum semantic binding:

```text
trust_domain / issuer
+
subject namespace
+
subject identifier
```

### T3 — Exact request-event identity

Must establish which externally rooted request-origin event is being referenced.

### T4 — Exact decision-event identity

Must establish which externally rooted decision event is being referenced.

### T5 — Event-content / revision integrity

Must establish the exact content or immutable revision associated with the event.

```text
EVENT IDENTITY != EVENT CONTENT IDENTITY
```

A mutable current record behind a stable event ID is insufficient.

### T6 — Exact decision-request binding

The decision event must bind to exact `decision_request_sha256` or an equivalent immutable transaction identity.

### T7 — Direct-principal action provenance

Must distinguish:

```text
principal directly acted
```

from:

```text
service / automation acted for principal
```

A service credential must not be able to manufacture an event accepted as the human's direct `ACCEPT`.

### T8 — Independent evidence integrity

Executor must validate the evidence without trusting a caller-generated `valid=true` or `VERIFIED` label.

### T9 — Freshness / validity

Must support the validity semantics required by the canonical trust profile for the freeze attempt.

### T10 — No Executor identity ownership

The mechanism must preserve:

```text
EXECUTOR VERIFIES AUTHORITY
        !=
EXECUTOR OWNS IDENTITY AUTHORITY
```

### T11 — No runtime provider/verifier shopping

Caller, model, receipt, evidence content or decision adapter may not select a weaker issuer, verifier, endpoint or trust root.

### T12 — No authority-dimension promotion

A positive REQUEST_INTENT fact must not become WRITE / MERGE / DEPLOY / NETWORK / SECRET authority.

## 4. Evaluation vocabulary

```text
PASS
The class can directly satisfy the requirement under its normal trust semantics,
without inventing a new caller-controlled trust assertion.

PARTIAL
The class supplies a useful part of the requirement but requires a separate
trusted mechanism for the missing property.

FAIL
The class structurally fails the requirement as a complete first-slice boundary.

PROVIDER-DEPENDENT
The technology class can support the property, but the standard/class itself
does not guarantee it. A concrete provider must be adversarially verified.
```

No numeric score is used.

One critical `FAIL` is enough to reject a class as a **standalone** trust boundary even if it performs strongly elsewhere.

## 5. Candidate technology classes

This comparison deliberately evaluates classes rather than vendors.

### C0 — Executor-local session + approval button

Example shape:

```text
Executor session says user=P
+
Executor UI records button=ACCEPT
```

This is the baseline rejection case.

It may be acceptable as user experience, but not as the external trust root.

### C1 — OpenID Connect identity assertion only

Uses an external OpenID Provider to authenticate an end user and return an ID Token containing issuer/subject identity claims.

Useful primarily for:

```text
WHO authenticated?
WHICH issuer owns the subject namespace?
```

It does not by itself establish that the human directly approved an exact Executor decision request.

### C2 — WebAuthn / passkey ceremony directly at Executor as Relying Party

Uses a public-key credential scoped to the Executor Relying Party.

WebAuthn provides randomized challenge replay protection, RP scoping, user-presence semantics and optional user verification.

It is potentially strong for proving that an authenticator operation occurred in response to a fresh challenge.

However, a direct Executor RP normally owns the local account/credential mapping. WebAuthn user verification also does not by itself provide a concrete natural-person identity to the RP.

Therefore it is not, by itself, an external identity root for this model.

### C3 — External identity provider with fresh step-up / WebAuthn-backed authentication

The external provider owns the subject namespace and requires a fresh user-authentication ceremony before returning an assertion.

This improves identity rooting and freshness.

However, ordinary authentication still answers approximately:

```text
P authenticated now
```

not necessarily:

```text
P directly ACCEPTED exact decision request Q
```

unless the external provider also owns and records the exact transaction-approval event.

### C4 — OAuth Rich Authorization Request + protected authorization request

Uses a fine-grained authorization request such as OAuth Rich Authorization Requests (`authorization_details`), with request integrity protected using mechanisms such as JAR/PAR.

This class is useful because it can represent exact transaction details and let an external Authorization Server present those details for user consent while protecting the request from swapping/tampering.

The standards do not, by themselves, guarantee an independently consumable immutable human-decision event with the exact F-20/F-21 properties required by Executor.

Therefore this is a strong transaction-binding substrate but not automatically a complete trust boundary.

### C5 — External transaction-approval / consent service with immutable audit evidence

Abstract class:

```text
external service owns subject namespace
+
external service presents exact transaction/decision
+
human directly approves there
+
service records immutable/tamper-evident event
+
Executor independently verifies event/evidence
```

This class is intentionally technology-agnostic.

A concrete provider qualifies only if it can prove all required event, content, provenance and freshness properties without service impersonation or runtime provider shopping.

### C6 — External certificate-/key-backed human signature over exact decision digest

The human signs an exact canonical decision-request representation or digest using a key whose identity/trust is rooted outside Executor.

This class can strongly bind the signer operation to exact content.

It becomes a human-authority solution only if the external trust model also establishes:

```text
who the signer principal is
whether the credential is valid now
whether signing requires the principal's direct action
whether the request-origin event is bound to the same principal namespace
```

A raw cryptographic signature without those properties is only content authenticity.

### C7 — Verifiable Credential / signed claim artifact

An external issuer can issue tamper-evident claims about a subject, authority or event.

This is useful as an evidence container and for external issuer/subject semantics.

However, a credential that merely says `subject=P` or `role=...` does not prove a direct human decision event.

To satisfy this boundary, the issuer would need to issue or expose an exact event claim with the same direct-action and immutable-context properties required elsewhere.

### C8 — JWS / HTTP Message Signatures / generic signed message only

Cryptographic message-signing primitives can strongly protect exact content or selected message components.

They do not inherently establish:

```text
which natural principal owns the key
whether the signer action was direct human action
whether the signer is the request originator
whether the issuer/trust source is canonical
```

They are supporting primitives, not a complete trust boundary.

## 6. Comparison matrix

| Requirement | C0 Local session | C1 OIDC only | C2 WebAuthn @ Executor | C3 External IdP + step-up | C4 RAR + JAR/PAR | C5 External approval service | C6 External human signature | C7 VC / signed claim | C8 Generic signature |
|---|---|---|---|---|---|---|---|---|---|
| T1 Trust-domain identity | FAIL | PASS | FAIL | PASS | PASS | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PASS | PARTIAL |
| T2 Subject binding | FAIL | PASS | PARTIAL | PASS | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PASS | PARTIAL |
| T3 Request-event identity | FAIL | FAIL | FAIL | FAIL | PARTIAL | PROVIDER-DEPENDENT | PARTIAL | PROVIDER-DEPENDENT | PARTIAL |
| T4 Decision-event identity | FAIL | FAIL | PARTIAL | PARTIAL | PARTIAL | PROVIDER-DEPENDENT | PASS | PROVIDER-DEPENDENT | PARTIAL |
| T5 Event content/revision integrity | FAIL | FAIL | PARTIAL | PARTIAL | PASS for auth request; PARTIAL for human event | PROVIDER-DEPENDENT | PASS for signed content | PASS for credential content | PASS for signed content |
| T6 Exact decision-request binding | FAIL | FAIL | PARTIAL | PARTIAL | PASS for requested authorization details | PROVIDER-DEPENDENT | PASS | PROVIDER-DEPENDENT | PASS |
| T7 Direct-principal action provenance | FAIL | FAIL | PARTIAL | PARTIAL | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | FAIL unless event issuance proves it | FAIL |
| T8 Independent evidence integrity | FAIL | PASS | PASS cryptographically; identity root still local | PASS | PASS | PROVIDER-DEPENDENT | PASS | PASS | PASS |
| T9 Freshness / validity | FAIL | PASS for authentication token semantics | PASS for ceremony freshness | PASS for fresh authentication; approval freshness depends | PARTIAL | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PARTIAL |
| T10 Avoid Executor identity ownership | FAIL | PASS | FAIL as standalone identity root | PASS | PASS | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PASS | PARTIAL |
| T11 No runtime provider shopping | FAIL unless separately governed | PASS if issuer pinned | PASS only if RP/credential policy canonical | PASS if provider pinned | PASS if AS/profile pinned | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PASS if issuer/schema pinned | PASS if key/trust root pinned |
| T12 No authority-dimension promotion | FAIL unless separately enforced | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PROVIDER-DEPENDENT | PROVIDER-DEPENDENT | PARTIAL | PARTIAL |
| Standalone fit for first slice | REJECT | REJECT | REJECT | REJECT | REJECT AS STANDALONE | CANDIDATE CLASS | CANDIDATE CLASS | REJECT AS STANDALONE | REJECT AS STANDALONE |

## 7. Findings by class

### 7.1 C0 — Local session/button: reject as trust boundary

Reason:

```text
identity truth
+
event truth
+
verification
```

would all originate in the same Executor-controlled boundary.

That is F-19 by construction.

Local UI may still be useful later as a presentation surface, but it cannot be the sole authority evidence.

### 7.2 C1 — OIDC: strong identity substrate, insufficient decision proof

OpenID Connect gives an external issuer/subject namespace and authenticated end-user claims.

This directly addresses a large part of T1/T2 and can support freshness/replay protections.

But an ID Token is fundamentally an authentication result. It does not by itself prove that the human directly approved exact Executor decision request `Q`.

Therefore:

```text
OIDC IDENTITY
    = useful identity root
    != complete REQUEST_INTENT approval evidence
```

### 7.3 C2 — WebAuthn: strong ceremony proof, weak external identity ownership when Executor is RP

WebAuthn is attractive because the assertion ceremony is challenge-based, replay-resistant, scoped to a Relying Party and can require user verification/presence.

That makes it a strong candidate primitive for T4/T7-style properties.

But a direct Executor WebAuthn deployment still requires Executor to maintain the association between the external human concept and the RP-local credential/account.

In addition, WebAuthn user verification does not itself identify a unique natural person to the Relying Party.

So:

```text
WEBAUTHN
  strong action/authenticator ceremony primitive
  != independent external human identity root
```

### 7.4 C3 — External IdP + step-up: better, but authentication is still not transaction approval

Moving WebAuthn/passkey/step-up into an external IdP helps F-19 because the external IdP owns the identity namespace.

Still, a fresh external login can prove:

```text
P authenticated near time T
```

without proving:

```text
P directly approved exact Q
```

A complete boundary needs transaction-specific event evidence from the external domain, not only reauthentication.

### 7.5 C4 — RAR + JAR/PAR: strongest standardized transaction-request substrate in this comparison

OAuth Rich Authorization Requests can express structured, fine-grained authorization details, and the Authorization Server can use those details when asking the user for consent.

JAR/PAR can protect the authorization request against swapping/tampering and keep the exact requested context at the external Authorization Server.

This aligns strongly with T5/T6.

The remaining gap is evidence semantics:

```text
AS processed consent
    != automatically
Executor possesses immutable direct-human-action event evidence
```

A concrete Authorization Server would need to expose the latter under a pinned trust profile.

### 7.6 C5 — External transaction-approval service: best architectural fit, provider properties must be proven

This is the only class in the matrix whose intended purpose exactly matches the trust boundary:

```text
external identity
+
external transaction presentation
+
direct human decision
+
immutable event evidence
```

But the label alone proves nothing.

A provider must be rejected if:

- API/service credentials can create an event indistinguishable from human approval;
- event IDs point to mutable content without revision commitment;
- exact decision-request binding is absent;
- subject identity is local/ambiguous;
- freshness/revocation is unavailable where required;
- evidence cannot be verified independently;
- provider/verifier selection can be changed by caller input.

Therefore C5 is a **candidate class**, not a selected solution.

### 7.7 C6 — External human signature: strongest exact-content primitive, identity and action provenance remain trust questions

A human-controlled external signing ceremony over exact `decision_request_sha256` can make F-20 difficult because the signed content commitment is explicit.

It can also provide an independent decision-event artifact.

But the key itself is not automatically a human identity.

A viable first-slice signature mechanism needs an external trust chain that proves the signer binding, direct-principal action semantics, validity/freshness and same-principal relation to the request-origin event.

This class is therefore also a **candidate class**, but operationally heavier than a provider that already owns both request-origin and transaction-approval events.

### 7.8 C7/C8 — signed containers and primitives: useful components, not authority roots

Verifiable Credentials, JWS and HTTP Message Signatures are useful for expressing externally issued claims and protecting exact content.

They do not remove the need to decide:

```text
who is trusted issuer?
what human event occurred?
was it direct human action?
which exact request did it cover?
```

Treat them as transport/evidence primitives beneath the trust contract, not as the trust contract itself.

## 8. Technology combinations worth a later concrete spike

No provider is selected here.

Only two **architectural composition patterns** remain plausible enough for a concrete later spike.

### Pattern A — External transaction authority domain

```text
EXTERNAL TRUST DOMAIN
  owns principal identity
  owns request-origin event
  presents exact decision request / transaction
  records direct human ACCEPT
  emits immutable/tamper-evident event evidence
        ↓
EXECUTOR
  verifies pinned trust profile
  verifies event + payload commitment
  verifies same principal
  verifies exact Q
```

Potential implementation substrates may include an authorization/approval server with transaction-specific consent and independently consumable audit/evidence semantics.

### Pattern B — External identity root + external user signing ceremony

```text
EXTERNAL IDENTITY ROOT
  binds principal P
        +
EXTERNAL / USER-CONTROLLED SIGNING CEREMONY
  P directly signs exact Q
        +
EXTERNAL REQUEST-ORIGIN EVIDENCE
  P originated R
        ↓
EXECUTOR
  verifies same canonical subject binding
  verifies signed exact Q
  verifies request-origin event
```

This pattern is cryptographically explicit but may introduce more operational complexity and credential lifecycle concerns.

## 9. Current rejection set

Do not choose the following as the **complete** first-slice boundary:

```text
local session + button
OIDC alone
WebAuthn directly at Executor alone
fresh external login alone
RAR/JAR/PAR alone
Verifiable Credential alone
generic signature alone
```

Each can be useful as a component.

None alone proves the full fixed fact set.

## 10. Convenience Trust rejection rule

Any future technology proposal must be rejected when its argument has the form:

```text
technology does not expose required fact X
        ↓
therefore redefine X as whatever technology exposes
```

Correct direction:

```text
fixed requirement X
        ↓
can technology prove X?
        ↓
YES -> continue
NO / UNKNOWN -> reject or compose with an independent mechanism
```

## 11. Required provider-neutral spike questions

Before naming a provider, every candidate architecture must answer:

1. Where is the canonical subject namespace owned?
2. Can Executor/service credentials manufacture a human-looking approval event?
3. Does the event bind exact immutable content/revision, not only an event ID?
4. Can the decision event bind exact `decision_request_sha256`?
5. Is request-origin evidence available in the same canonical subject namespace?
6. Can request origin and decision actor be compared without account federation?
7. Is event validity/freshness independently checkable?
8. Can the caller select issuer/verifier/trust root?
9. Can provider unavailability trigger fallback?
10. Can the resulting REQUEST_INTENT proof be accidentally reused as resource/action authority?
11. Does verification depend on trusting an Executor-created `verified=true` artifact?
12. Can the event be edited after the human action while retaining the same identifier?
13. Can API/service action be distinguished from direct principal action?

Any unresolved answer means:

```text
NOT READY FOR IMPLEMENTATION
```

## 12. Sources used for technology properties

Primary standards/specifications used by this comparison:

- OpenID Connect Core 1.0 / current Errata Set 2 semantics for `iss`, `sub`, ID Tokens and end-user authentication.
- W3C Web Authentication Level 3 for RP-scoped credentials, user presence/verification, challenges and authenticator consent semantics.
- NIST SP 800-63B for phishing resistance, verifier binding and replay-resistant challenge/nonces.
- RFC 9396, OAuth 2.0 Rich Authorization Requests, for fine-grained `authorization_details` and consent semantics.
- RFC 9101 / RFC 9126 concepts for protected / pushed authorization requests and request integrity.
- RFC 9421, HTTP Message Signatures, as an example of content-authentication/signature primitives that do not themselves supply human authority semantics.
- W3C Verifiable Credentials Data Model 2.x as an example of externally issued verifiable claim containers.

Standards describe protocol properties. They do not constitute acceptance of any concrete provider implementation.

## 13. Current conclusion

The comparison does **not** justify choosing a provider yet.

It does justify narrowing the next practical research to two architecture classes:

```text
A. external transaction-approval authority domain

or

B. external identity root + human signing ceremony
```

The next step should compare concrete realizations of A and B against the same fixed matrix, with no requirement changes.

Until a concrete mechanism proves all mandatory first-slice facts:

```text
IMPLEMENTATION = NOT STARTED
AUTHORIZED_AND_FROZEN = FORBIDDEN
```
