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

This regression is about **actor identity, authoritative write receipts, durable evidence binding, and independent observation provenance**, not about JDTLS behavior.

The original failure to prevent is:

```text
SYSTEM WRITE ATTEMPT
  -> AUTHORITATIVE FAILURE RECEIPT
  -> HUMAN PERFORMS OR CLAIMS A SEPARATE MANUAL ACTION
  -> SYSTEM LANGUAGE/STATE COLLAPSES BOTH ACTORS
  -> HUMAN CLAIM IS TREATED AS IF IT COMPLETED THE SYSTEM ACTION
```

The hardening added after adversarial review also prevents these adjacent false-success paths:

```text
RAW DICT
  -> caller labels it "success"
  -> SYSTEM_COMPLETED

SUCCESS RESPONSE
  -> object identity points at a different provider target
  -> SYSTEM_COMPLETED

SUCCESS RESPONSE
  -> no durable evidence write
  -> SYSTEM_COMPLETED

BOOLEAN "observed=true"
  -> no object/effect/read evidence
  -> HUMAN_REPORTED / OBSERVED
```

## 2. Canonical fixture

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

The fixture stores:
- the intended effect body;
- the raw provider response bytes as deterministic fixture text;
- the expected SHA-256 of the intended effect;
- the expected SHA-256 of the provider response.

The hashes are derived from bytes. They are not caller-declared authority.

## 3. Correct state machine

```text
SYSTEM_WRITE_REQUESTED
       |
       v
SYSTEM_WRITE_ATTEMPTED
       |
       v
TRUSTED PROVIDER GATEWAY
       |
       +--> raw provider response bytes
       +--> attempted effect bytes
       +--> provider status/message
       +--> provider object identity when success
       |
       v
VALIDATE PROVIDER/TARGET/OBJECT BINDING
       |
       v
PERSIST CONTENT-ADDRESSED RECEIPT EVIDENCE
       |
       v
READ-AFTER-WRITE VERIFY PERSISTED EVIDENCE
       |
       v
VerifiedExternalEffectReceipt
       |
       +-------------------------------+
       |                               |
 failure receipt                   success receipt
       |                               |
       v                               v
SYSTEM_FAILED                    SYSTEM_COMPLETED
                                       |
                                       v
                          INDEPENDENT_READ_REQUIRED
```

A later HUMAN action is a separate branch:

```text
HUMAN_MANUAL_ACTION_CLAIMED
       |
       v
HUMAN_REPORTED / UNVERIFIED
       |
       v
TRUSTED VERIFIER GATEWAY
       |
       +--> provider response bytes
       +--> exact provider object identity
       +--> exact observed effect bytes
       +--> observation timestamp
       |
       v
PERSIST + VERIFY OBSERVATION EVIDENCE
       |
       v
VerifiedExternalObservation
       |
       v
provider + target + object + effect all match?
        /                           \
      NO                             YES
      |                               |
      v                               v
HUMAN_REPORTED /              HUMAN_REPORTED /
   UNVERIFIED                      OBSERVED
```

The SYSTEM branch never changes because of a later HUMAN event.

## 4. Invariants

### INV-AR1 — SYSTEM WRITE COMPLETION

A system-performed mutating action may reach `COMPLETED` only if all of the following hold:

1. the receipt is a `VerifiedExternalEffectReceipt`;
2. it was minted through the trusted provider-gateway boundary, not from a caller dictionary;
3. `response_sha256` was computed from the actual provider response bytes;
4. `effect_sha256` binds the exact attempted mutation payload;
5. a successful response carries durable provider object identity;
6. provider, action kind, target, object id and object URL are mutually consistent;
7. the receipt evidence was durably persisted;
8. the persisted evidence passes read-after-write verification.

```text
NO RECEIPT = NO SYSTEM COMPLETION CLAIM
RAW DICT != AUTHORITATIVE RECEIPT
FAILURE RECEIPT = SYSTEM FAILED
SUCCESS WITHOUT OBJECT IDENTITY = INVALID
SUCCESS WITHOUT DURABLE PERSISTENCE = INVALID
SUCCESS WITH WRONG TARGET/OBJECT BINDING = INVALID
```

A successful receipt establishes SYSTEM write completion only. It does not establish terminal PASS.

### INV-AR2 — ACTOR BINDING

A human-reported external action remains:

`HUMAN_REPORTED / UNVERIFIED`

until a `VerifiedExternalObservation` independently binds:

- provider;
- action kind;
- target;
- provider object identity;
- observed effect fingerprint;
- observation response fingerprint;
- observation timestamp;
- durable observation evidence.

A bare boolean is not verification.

```text
BOOLEAN OBSERVED != VERIFIED OBSERVATION
WRONG TARGET != OBSERVATION OF CLAIMED EFFECT
WRONG EFFECT HASH != OBSERVATION OF CLAIMED EFFECT
```

A HUMAN claim must never inherit `SYSTEM_COMPLETED`, `SYSTEM_SUCCESS`, or a SYSTEM receipt.

### INV-AR3 — EVIDENCE NON-SUBSTITUTION

Human-supplied recovery evidence may support a separate forensic or verification path, but must not retroactively:

- repair a missing SYSTEM receipt;
- replace an authoritative SYSTEM failure receipt;
- convert a failed/unverified SYSTEM execution into PASS;
- rewrite the actor that performed the action.

## 5. Authority boundary

Public assessment functions accept only verified evidence objects:

- `assess_system_write(...)`
- `assess_actor_receipt_provenance(...)`

Raw dictionaries cannot be promoted into authoritative receipts.

`VerifiedExternalEffectReceipt` and `VerifiedExternalObservation` reject direct normal construction. Their proof field is non-init, so `dataclasses.replace(...)` cannot silently carry authority to a modified object.

The current PR intentionally does **not** add a live external mutation adapter. Private persistence hooks represent the trusted provider/verifier gateway boundary for deterministic regression tests and future adapter wiring:

- `_persist_verified_system_write_receipt(...)`
- `_persist_verified_external_observation(...)`

Production adapter-wide integration remains a separate scope and is not claimed here.

## 6. Provider binding implemented in this candidate

The bounded provider binding implemented by ARP-001 is:

```text
provider    = GITHUB
action_kind = CREATE_ISSUE_COMMENT
target      = owner/repo#issue
```

For successful GitHub comment writes and observations:

- `object_id` must be a positive integer string;
- `object_url` must be HTTPS on `github.com`;
- URL path must equal `/owner/repo/issues/<issue>`;
- URL fragment must equal `issuecomment-<object_id>`;
- URL credentials/query substitutions are rejected.

Unsupported provider/action bindings fail closed.

This is intentionally not an adapter-wide capability claim.

## 7. Durable evidence contract

Receipt and observation gateways persist a content-addressed JSON evidence envelope containing:

- exact normalized metadata;
- base64 of the provider response bytes.

The envelope itself has a SHA-256 identity.

Before a verified receipt or observation is accepted by the state assessment:

1. the evidence file must still exist as one regular file;
2. its bytes must match its persisted evidence SHA-256;
3. its normalized payload must equal the verified object;
4. the stored provider response bytes must hash to the bound `response_sha256`.

If the evidence is missing or modified, the result fails closed to `UNVERIFIED / INVALID`.

## 8. Expected assertions for ARP-001

For the historical 403 flow the verifier must assert:

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

It must additionally preserve:
- exact provider failure message;
- response SHA derived from raw provider bytes;
- effect SHA derived from exact intended effect bytes;
- durable receipt evidence reference.

## 9. Required adversarial regression set

The test suite must cover at least:

```text
A1  403 is authoritative failure, not missing/ambiguous receipt
A2  raw dict cannot become authoritative receipt
A3  direct VerifiedExternalEffectReceipt construction is rejected
A4  dataclasses.replace cannot carry authority to modified receipt
A5  success without object identity is rejected
A6  wrong provider host is rejected
A7  wrong repository is rejected
A8  wrong issue is rejected
A9  object_id != URL fragment comment id is rejected
A10 response_sha256 is computed from actual provider response bytes
A11 persisted receipt tamper invalidates completion
A12 valid success can reach SYSTEM_COMPLETED but not terminal PASS
A13 valid independent observation can mark HUMAN event OBSERVED
A14 observation of wrong target stays UNVERIFIED
A15 observation of wrong effect stays UNVERIFIED
A16 string/truthy boolean shortcuts are rejected
A17 direct VerifiedExternalObservation construction is rejected
```

## 10. Forbidden outcomes for the ARP-001 403 flow

Any of these outcomes in the historical/synthetic ARP-001 403 flow is a regression failure. A separately verified successful SYSTEM write may legitimately reach `SYSTEM_COMPLETED` as specified by A12, but still cannot reach terminal PASS without independent verification.

```text
SYSTEM_COMPLETED_FOR_ARP001_403_FLOW
SYSTEM_PASS
ACTION_COMPLETED            # if it collapses actor provenance
RAW_DICT_BECOMES_AUTHORITATIVE
CALLER_MINTS_VERIFIED_RECEIPT
SUCCESS_WITHOUT_DURABLE_PERSISTENCE
SUCCESS_WITH_WRONG_TARGET_OBJECT_IDENTITY
CALLER_SUPPLIED_RESPONSE_HASH_TREATED_AS_PROOF
BOOLEAN_OBSERVATION_SHORTCUT
WRONG_OBJECT_COUNTS_AS_OBSERVED
WRONG_EFFECT_COUNTS_AS_OBSERVED
HUMAN_CLAIM_INHERITS_SYSTEM_STATUS
HUMAN_CLAIM_REPLACES_SYSTEM_RECEIPT
FAILED_SYSTEM_WRITE_RETROACTIVELY_REPAIRED
403_TREATED_AS_MISSING_RECEIPT
403_TREATED_AS_AMBIGUOUS_WRITE_OUTCOME
OBJECT_ID_REQUIRED_FOR_FAILED_WRITE
TERMINAL_PASS_WITHOUT_BOUND_INDEPENDENT_VERIFICATION
```

## 11. Language regression

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

## 12. Relationship to Orphaned Side Effect

ARP-001 is **not** an Orphaned Side Effect.

Reserve `ORPHANED SIDE EFFECT` for the stricter mechanism:

```text
SYSTEM WRITE
  -> AUTHORITATIVE SUCCESS RECEIPT / EFFECT CREATED
  -> DURABLE OBJECT IDENTITY EXISTS AT PROVIDER
  -> EXECUTOR LOSES OR FAILS TO PERSIST id/url BEFORE EVIDENCE BINDING
```

That failure needs its own fixture when observed or intentionally falsified. ARP-001 does not claim to close FAI-009.

## 13. Evidence non-repair rule

This regression must remain reproducible without:

- a live provider write;
- retrying the failed mutation;
- a human-provided permalink;
- modifying the external issue;
- changing the historical 403 receipt.

The synthetic fixture is sufficient to prove the ARP-001 state-machine and authority-boundary rules.

## 14. Acceptance boundary for PR #83

PR #83 can be considered technically ready for human acceptance only when:

```text
- ARP-001 deterministic tests pass;
- the full Executor foundation suite passes on the exact PR head;
- GP001 replay repeatability passes on the exact PR head;
- no live provider write is required to prove the regression;
- PR remains draft/unmerged until separate human acceptance;
- no claim is made that all provider adapters are wired to this boundary.
```
