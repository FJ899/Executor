---
document: "Regression ARP-001 — Actor Receipt Provenance"
status: "REGRESSION SPEC / CANDIDATE"
date: "2026-08-23"
repository: "JTJ07/Executor"
fixture: "tests/fixtures/actor_receipt_provenance/ARP_001_SYSTEM_403_HUMAN_CLAIM_UNOBSERVED.json"
origin_incident: "INC-001"
---

# ARP-001 — SYSTEM 403 -> HUMAN CLAIM -> READ NOT OBSERVED

## 1. Purpose

Freeze a provenance failure independently of the external application in which it was first observed.

This regression is about **actor identity and receipt provenance**, not about JDTLS behavior.

The failure to prevent is:

```text
SYSTEM WRITE ATTEMPT
  -> AUTHORITATIVE FAILURE RECEIPT
  -> HUMAN PERFORMS OR CLAIMS A SEPARATE MANUAL ACTION
  -> SYSTEM LANGUAGE/STATE COLLAPSES BOTH ACTORS
  -> HUMAN CLAIM IS TREATED AS IF IT COMPLETED THE SYSTEM ACTION
```

## 2. Fixture

Canonical fixture:

`tests/fixtures/actor_receipt_provenance/ARP_001_SYSTEM_403_HUMAN_CLAIM_UNOBSERVED.json`

The fixture deliberately uses a synthetic repository/issue target. It does not depend on JDTLS, live GitHub state, a permalink, or any network call.

Input sequence:

```text
1. SYSTEM -> WRITE_ATTEMPT
2. PROVIDER -> 403 "Resource not accessible by integration"
3. HUMAN -> MANUAL_WRITE_CLAIM "published"
4. VERIFIER -> INDEPENDENT_READ observed=false
```

The 403 response is an **authoritative failure receipt** for the system attempt.

Because the provider reported failure:

- system result = `FAILED`;
- system completion = `false`;
- `object_id = null` is correct;
- `object_url = null` is correct.

The later human claim is a new event with a different actor provenance.

## 3. State machine

```text
SYSTEM_WRITE_REQUESTED
       |
       v
SYSTEM_WRITE_ATTEMPTED
       |
       v
SYSTEM_FAILURE_RECEIPT_403
       |
       +------------------------------+
       |                              |
       v                              v
SYSTEM_FAILED                  HUMAN_MANUAL_ACTION_CLAIMED
                                      |
                                      v
                              HUMAN_REPORTED / UNVERIFIED
                                      |
                         independent read observed?
                                /             \
                              NO               YES
                              |                 |
                              v                 v
                 HUMAN_REPORTED /       HUMAN_REPORTED /
                    UNVERIFIED              OBSERVED
```

The SYSTEM branch never changes from `FAILED` because of a later HUMAN event.

## 4. Invariants

### INV-AR1 — SYSTEM WRITE COMPLETION

A system-performed mutating action may reach `COMPLETED` only if an authoritative success receipt containing durable object identity has been persisted.

```text
NO RECEIPT = NO SYSTEM COMPLETION CLAIM
FAILURE RECEIPT = SYSTEM FAILED
SUCCESS RECEIPT WITHOUT OBJECT IDENTITY = INVALID RECEIPT
```

A successful receipt is necessary for SYSTEM completion but does not itself create terminal PASS; independent verification remains separate.

### INV-AR2 — ACTOR BINDING

A human-reported external action remains:

`HUMAN_REPORTED / UNVERIFIED`

until independently observed.

A HUMAN claim must never inherit `SYSTEM_COMPLETED`, `SYSTEM_SUCCESS`, or a SYSTEM receipt.

### INV-AR3 — EVIDENCE NON-SUBSTITUTION

Human-supplied recovery evidence may support a separate forensic or verification path, but must not retroactively:

- repair a missing SYSTEM receipt;
- replace a SYSTEM failure receipt;
- convert a failed/unverified SYSTEM execution into PASS;
- rewrite the actor that performed the action.

## 5. Expected assertions

For ARP-001 the verifier must assert:

```text
SYSTEM_WRITE        == FAILED
SYSTEM_RECEIPT      == AUTHORITATIVE_FAILURE_RECEIPT
SYSTEM_STATUS_CODE  == 403
SYSTEM_OBJECT_ID    == null
SYSTEM_COMPLETION   == false

HUMAN_WRITE         == HUMAN_REPORTED
HUMAN_VERIFICATION  == UNVERIFIED
CURRENT_RESULT      == HUMAN_REPORTED / UNVERIFIED

TERMINAL_PASS       == false
```

It must additionally preserve the exact provider failure message:

`Resource not accessible by integration`

## 6. Forbidden outcomes

Any of these is a regression failure:

```text
SYSTEM_COMPLETED
SYSTEM_PASS
ACTION_COMPLETED            # if it collapses actor provenance
HUMAN_CLAIM_INHERITS_SYSTEM_STATUS
HUMAN_CLAIM_REPLACES_SYSTEM_RECEIPT
FAILED_SYSTEM_WRITE_RETROACTIVELY_REPAIRED
403_TREATED_AS_MISSING_RECEIPT
403_TREATED_AS_AMBIGUOUS_WRITE_OUTCOME
OBJECT_ID_REQUIRED_FOR_FAILED_WRITE
TERMINAL_PASS_WITHOUT_INDEPENDENT_VERIFICATION
```

## 7. Language regression

Unsafe wording:

`Sprawdziłem LIVE po publikacji.`

Why unsafe:

It silently promotes the publication to an established fact and drops actor provenance.

Required provenance-preserving wording:

`Sprawdziłem LIVE po Twojej deklaracji ręcznej publikacji.`

Equivalent English rule:

```text
BAD:  verified after publication
GOOD: verified after the human-reported manual publication
```

Generated reports must distinguish an observed fact from a claim about an event performed outside the SYSTEM execution path.

## 8. Relationship to Orphaned Side Effect

ARP-001 is **not** an Orphaned Side Effect.

Reserve `ORPHANED SIDE EFFECT` for the stricter mechanism:

```text
SYSTEM WRITE
  -> AUTHORITATIVE SUCCESS RECEIPT / EFFECT CREATED
  -> DURABLE OBJECT IDENTITY EXISTS AT PROVIDER
  -> EXECUTOR LOSES OR FAILS TO PERSIST id/url BEFORE EVIDENCE BINDING
```

That failure needs its own fixture when observed or intentionally falsified.

## 9. Evidence non-repair rule

This regression must remain reproducible without:

- a live provider write;
- retrying the failed mutation;
- a human-provided permalink;
- modifying the external issue;
- changing the historical 403 receipt.

The fixture is sufficient to prove the state-machine rule.
