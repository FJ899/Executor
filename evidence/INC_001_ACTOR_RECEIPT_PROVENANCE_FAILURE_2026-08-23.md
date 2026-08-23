---
document: "INC-001 Actor Receipt Provenance Failure"
status: "OBSERVED / HUMAN-REPORTED UNVERIFIED"
date: "2026-08-23"
repository: "JTJ07/Executor"
real_environment: "eclipse-jdtls/eclipse.jdt.ls#3866"
regression_case: "ARP-001"
---

# INC-001 — Actor Receipt Provenance Failure

## 1. Corrected incident classification

This incident is **not** an Orphaned Side Effect.

The system write attempt had an authoritative provider failure receipt:

```text
HTTP 403
Resource not accessible by integration
```

Therefore the system action outcome was known:

`FAILED WITH AUTHORITATIVE FAILURE RECEIPT`

No system-created `object_id` or `object_url` should exist for that failed attempt.

A later human statement — `opublikowane` / `published` — referred to a separate manual action outside the failed SYSTEM write path.

## 2. Actor-separated event sequence

```text
SYSTEM WRITE ATTEMPT
  -> PROVIDER 403 FAILURE RECEIPT
  -> SYSTEM_WRITE = FAILED
  -> HUMAN MANUAL ACTION CLAIM = "published"
  -> INDEPENDENT READ DOES NOT OBSERVE THE CLAIMED NEW OBJECT
  -> CURRENT RESULT = HUMAN_REPORTED / UNVERIFIED
  -> TERMINAL PASS = FORBIDDEN
```

The HUMAN event must never inherit the SYSTEM action's identity or status.

## 3. Corrected evidence table

| Field | State |
|---|---|
| `SYSTEM_WRITE` | `FAILED` |
| `SYSTEM_RECEIPT` | `403 Resource not accessible by integration` |
| `SYSTEM_OBJECT_ID` | none; correct because SYSTEM creation failed |
| `SYSTEM_OBJECT_URL` | none; correct because SYSTEM creation failed |
| `HUMAN_WRITE_CLAIM` | `published` |
| `HUMAN_WRITE_RECEIPT` | unavailable to SYSTEM |
| `INDEPENDENT_READ` | claimed new comment not observed |
| `CURRENT_RESULT` | `HUMAN_REPORTED / UNVERIFIED` |
| `TERMINAL_PASS` | `FORBIDDEN` |

No retry or duplicate publication is part of this incident record.
No human permalink is required to preserve the regression.

## 4. Failure mechanism

Primary failure class:

`FAI-008 — ACTOR-RECEIPT PROVENANCE FAILURE`

Failure boundary:

```text
SYSTEM ACTION
  -> AUTHORITATIVE FAILURE RECEIPT
  -> HUMAN REPORTS SEPARATE MANUAL ACTION
  -> LANGUAGE OR STATE COLLAPSES ACTOR PROVENANCE
  -> HUMAN CLAIM RISKS BEING TREATED AS SYSTEM COMPLETION
```

The dangerous transition is not receipt loss. The dangerous transition is **receipt/status inheritance across actors**.

## 5. Corrected language finding

Overstated wording:

`Sprawdziłem LIVE po publikacji.`

Correct provenance-preserving wording:

`Sprawdziłem LIVE po Twojej deklaracji ręcznej publikacji.`

The first wording treats publication as established system knowledge. The second records exactly what was known: a HUMAN claim preceded the read-only verification.

## 6. Invariants

### INV-AR1 — SYSTEM WRITE COMPLETION

A SYSTEM mutating action may reach `COMPLETED` only if an authoritative success receipt containing durable object identity has been persisted.

`NO RECEIPT = NO SYSTEM COMPLETION CLAIM.`

An authoritative failure receipt such as HTTP 403 means the SYSTEM action is `FAILED`, not ambiguous and not completed.

### INV-AR2 — ACTOR BINDING

A human-reported external action remains:

`HUMAN_REPORTED / UNVERIFIED`

until independently observed.

A HUMAN claim must never inherit `SYSTEM_COMPLETED` status.

### INV-AR3 — EVIDENCE NON-SUBSTITUTION

Human-supplied recovery evidence may support a separate forensic investigation, but must not retroactively repair a missing SYSTEM receipt, replace a SYSTEM failure receipt, or convert a failed/unverified execution into PASS.

## 7. Regression extraction

The incident has been extracted into a provider-independent deterministic regression:

- spec: `docs/safety/REGRESSION_ARP_001_ACTOR_RECEIPT_PROVENANCE.md`;
- fixture: `tests/fixtures/actor_receipt_provenance/ARP_001_SYSTEM_403_HUMAN_CLAIM_UNOBSERVED.json`;
- assertions: `tests/test_external_effect_receipt.py`.

The fixture does not depend on JDTLS or current GitHub state.

## 8. Reserved adjacent failure class

`ORPHANED SIDE EFFECT` is reserved for a stricter future/adversarial case:

```text
SYSTEM WRITE SUCCEEDS
  -> PROVIDER RETURNS DURABLE OBJECT IDENTITY
  -> EFFECT EXISTS
  -> EXECUTOR FAILS TO PERSIST OR RETAIN THE SUCCESS RECEIPT
```

That is a distinct failure and must not be inferred from INC-001.
