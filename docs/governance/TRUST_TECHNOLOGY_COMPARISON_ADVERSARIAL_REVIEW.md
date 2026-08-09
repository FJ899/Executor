---
document: "Trust Technology Comparison Adversarial Review"
version: "0.1"
status: "DRAFT / ADVERSARIAL REVIEW / NO TECHNOLOGY SELECTION"
date: "2026-08-09"
repository: "litrgratis-pixel/Executor"
depends_on:
  - "docs/governance/TRUST_TECHNOLOGY_COMPARISON.md"
---

# Trust Technology Comparison Adversarial Review v0.1

## 1. Purpose

This review attacks the comparison before any provider or implementation is selected.

It does not replace the fixed requirements.

It asks whether either surviving architecture class could still appear compliant while silently weakening the human-authority semantics.

## 2. Finding F-22 — Retroactive Request-Origin Attribution

### Failure

```text
request enters Executor without externally rooted origin identity
        ↓
later principal P authenticates / approves
        ↓
system attaches P to the old request
        ↓
system claims:
"P originated request R"
```

The later authentication event may be real.

The approval event may be real.

The request text may be exact.

But the historical origin claim was never externally established when the request entered the governed chain.

Core invariant:

> **LATER AUTHENTICATION != PROOF OF EARLIER REQUEST ORIGINATION.**

and:

```text
RETROACTIVE SUBJECT ATTACHMENT
        !=
EXTERNALLY VERIFIED REQUEST-ORIGIN EVENT
```

### Required behavior

The first concrete architecture must do one of the following:

```text
A. capture the governed request inside the canonical external trust domain
   so request-origin event R is externally identity-bound at creation;

or

B. create an externally verifiable user-controlled origin assertion/event
   at request intake that binds principal P to the exact governed request identity.
```

What is not allowed:

```text
unbound request now
+
verified user later
=
pretend verified origin
```

### Consequence for current architecture candidates

Pattern A becomes stronger if the external transaction/authority domain also owns or records request intake.

Pattern B requires an explicit externally rooted request-origin ceremony at intake; signing only the later approval is insufficient.

## 3. Finding F-23 — Review / Signing Surface Substitution

### Failure

```text
Executor displays human-readable review A
        ↓
external signer receives opaque digest Q for different review/contract B
        ↓
human performs a real signing gesture
        ↓
signature over Q is valid
        ↓
system claims human reviewed B
```

This can satisfy:

```text
real human action
real signature
exact digest integrity
```

while still failing the semantic human-review boundary.

Core invariant:

> **DIRECT SIGNING ACTION != PROOF OF REVIEWED MEANING WHEN THE SIGNED IDENTITY IS NOT TRUSTEDLY BOUND TO WHAT THE HUMAN SAW.**

and:

```text
SIGNED HASH B
+
DISPLAYED MATERIAL A
        !=
INFORMED APPROVAL OF B
```

### Required behavior

A signature-oriented solution must provide a trustworthy relationship between:

```text
human-readable review material
+
machine-verifiable review identity
+
decision-request identity
+
signed transaction identity
```

The trusted ceremony must prevent Executor from independently choosing:

```text
what the human sees
```

and a different:

```text
what the human signs
```

without detection.

A mechanism that only asks the user to authenticate/sign an opaque challenge is insufficient to prove informed approval of the bound contract meaning.

## 4. Revised architecture comparison

### Pattern A — External transaction-approval authority domain

Current status:

```text
STRONGER FIRST-SLICE FIT
PROVIDER NOT SELECTED
```

Why:

A qualifying external domain can potentially own all of the human-facing facts that must remain outside Executor:

```text
principal identity
request-origin event
exact decision/transaction presentation
direct human ACCEPT event
immutable event content/revision
```

Executor can remain verifier of exported evidence rather than owner of the identity/event truth.

Pattern A still fails unless a concrete provider demonstrates:

- request intake/origin binding, not only approval;
- exact transaction/review presentation binding;
- F-20 immutable event-content/revision evidence;
- F-21 direct-principal action provenance;
- no service impersonation;
- independent evidence verification;
- canonical provider/trust-profile pinning;
- freshness/status semantics.

### Pattern B — External identity root + human signing ceremony

Current status:

```text
CONDITIONAL CANDIDATE
NOT YET EQUIVALENT TO PATTERN A
```

It remains viable only if it additionally solves both new findings:

```text
F-22 request origin must be externally bound at intake
+
F-23 trusted review/signing display binding
```

A signature over exact `decision_request_sha256` is not enough if:

- request origin was attached retroactively;
- the user cannot verify what exact semantic review material the signed digest represents;
- the signing service can sign on behalf of the user without direct user action;
- identity/signing namespace cannot be compared with request-origin evidence.

Therefore Pattern B is no longer treated as equally minimal.

## 5. Revised first-slice technology direction

No provider is selected.

But the architecture ordering after adversarial review is now:

```text
1. PREFERRED RESEARCH CLASS
   External transaction-approval authority domain
   that can own both request-origin and exact approval-event truth.

2. SECONDARY / CONDITIONAL CLASS
   External identity + signing ceremony
   only if trusted display binding and externally rooted request intake are proven.
```

This is not a product decision to implement Pattern A.

It is only a research priority based on the fixed trust contract.

## 6. Additional rejection tests for any concrete mechanism

A candidate is rejected if any answer is unresolved:

1. Was request-origin identity bound at the time the governed request entered the chain?
2. Can a later login/approval be incorrectly used to backfill request ownership?
3. Does the human see the exact semantic content that is machine-bound to the decision event?
4. Can Executor show one review and cause another digest/transaction to be approved?
5. Does a signing/authentication ceremony prove only possession/presence, or the exact transaction meaning?
6. Can the external trust domain export immutable request-origin and decision-event evidence?
7. Are request origin and approval comparable inside one canonical subject namespace without local account linking?
8. Can service/API credentials create events indistinguishable from direct human actions?

Any unresolved item means:

```text
NOT READY FOR IMPLEMENTATION
```

## 7. Failure map extension

```text
F-19 Trust Boundary Collapse
F-20 Event Payload Rebinding / Mutable Event Drift
F-21 Action-Provenance Confusion
F-22 Retroactive Request-Origin Attribution
F-23 Review / Signing Surface Substitution
```

F-22 and F-23 should be reconciled into the superior trust-boundary/model documents before those documents are ever merged.

They do not authorize implementation.

## 8. Standards interpretation note

The comparison remains consistent with the standards reviewed:

- OIDC is an authentication/identity substrate and does not, by itself, provide exact Executor transaction approval.
- WebAuthn provides RP-bound, challenge-based authenticator ceremonies with user presence/verification semantics, but its user-verification semantics do not themselves identify a unique natural person to the RP, and the ceremony does not automatically prove the application-specific review meaning shown outside the authenticator.
- OAuth RAR can carry fine-grained authorization details that the Authorization Server can present for consent; JAR/PAR can strengthen request integrity. A concrete Authorization Server still needs independently verifiable event semantics satisfying F-20/F-21/F-22.
- Generic signatures can authenticate exact signed content, but signer identity, human-action provenance, request origin and review-surface binding remain separate trust properties.

## 9. Gate

```text
PR #55: UNDER ADVERSARIAL REVIEW
PROVIDER: NOT SELECTED
IMPLEMENTATION: NOT STARTED

F-22: DEFINED
F-23: DEFINED

PATTERN A: PREFERRED RESEARCH CLASS
PATTERN B: CONDITIONAL RESEARCH CLASS

NEXT:
USER DECISION — ACCEPT COMPARISON DIRECTION OR CONTINUE TECHNOLOGY REVIEW
```
