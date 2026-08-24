---
document: "Regression OSE-001 — Orphaned Side Effect"
status: "REGRESSION SPEC / CANDIDATE / AUDIT-R2-REPAIRED"
date: "2026-08-23"
repository: "JTJ07/Executor"
failure_class: "FAI-009"
fixture: "tests/fixtures/orphaned_side_effect/OSE_001_PROVIDER_SUCCESS_CRASH_BEFORE_RECEIPT.json"
stacked_on: "rework/external-effect-receipt-2026-08-23@0c592646066d98dd55a8cdc780e2215024f26b83"
---

# OSE-001 — PROVIDER SUCCESS -> CRASH BEFORE RECEIPT PERSISTENCE

## 1. Purpose

Freeze the ambiguity window that remains after ARP-001:

```text
SYSTEM durably reserves one exact pre-write attempt
  -> trusted boundary mints a fresh recovery correlation nonce
  -> provider may perform a non-idempotent mutation
  -> provider may return a result / durable object identity
  -> process crashes or exact attempt/result persistence fails
  -> the external effect may exist while local state is ambiguous
```

The safety question is not whether the provider probably created the object. It is whether Executor can prove which exact attempt produced which exact external result before it permits completion, clean failure, or retry.

This regression is synthetic. It does not call GitHub, add a live mutation adapter, publish a comment, merge a PR, or claim provider-wide recovery support.

## 2. Failure class

`FAI-009 — ORPHANED SIDE EFFECT / SUCCESS RECEIPT LOSS`

Forbidden collapse:

```text
PROVIDER MAY HAVE CREATED EFFECT
  -> LOCAL ATTEMPT/RESULT BINDING IS MISSING OR AMBIGUOUS
  -> SYSTEM SAYS FAILED
  -> AUTOMATIC RETRY
  -> DUPLICATE EXTERNAL EFFECT
```

Also forbidden:

```text
ATTEMPT B -> reuse result from ATTEMPT A -> COMPLETED / FAILED
ONE ATTEMPT -> two different durable results -> caller chooses outcome
HTTP 5xx -> clean no-effect failure
PRE-EXISTING OBJECT -> matching body/correlation -> recovered as new attempt
EVIDENCE ROOT A -> result/scan substituted from ROOT B
```

## 3. Correct state machine

Before provider entry:

```text
INTENT / AUTHORITY
      |
      v
DURABLE EVIDENCE ROOT
  - newly-created directory entries fsynced
      |
      v
TRUSTED ATTEMPT NONCE MINT
  - random 128-bit correlation nonce
  - caller does not supply attempt_id
      |
      v
ATOMIC ATTEMPT-ID RESERVATION
  - provider
  - action kind
  - exact target
  - exact effect SHA-256
  - minted attempt_id
  - started_at
  - retry_policy = FORBIDDEN_WHILE_UNRESOLVED
      |
      v
WRITE_IN_FLIGHT
      |
      v
PROVIDER WRITE
```

Normal provider result:

```text
PROVIDER RESULT
      |
      v
ARP-001 VERIFIED PROVIDER RECEIPT
      |
      v
ONE IMMUTABLE ATTEMPT RESULT SLOT
  external_effect_attempt_result-<attempt_id>.json
      |
      +--> identical replay = idempotent
      +--> conflicting second result = RECOVERY REQUIRED / FAIL CLOSED
```

The receipt file, attempt journal, result binding, and accepted recovery scan must all live in the same authoritative evidence root.

## 4. Provider-result semantics

ARP-001 proves that a provider response is authentic evidence of the response that was received. OSE-001 asks the additional causal question: does that response safely prove the external effect state?

For the bounded GitHub issue-comment model:

```text
2xx + valid object identity
  -> SUCCESS

explicitly classified no-effect 4xx
  -> DEFINITIVE_FAILURE

5xx or any unclassified status
  -> AMBIGUOUS
  -> RECOVERY_REQUIRED / POSSIBLY_CREATED
```

A 5xx receipt may be authoritative evidence that the provider returned 5xx; it is not proof that a non-idempotent mutation did not happen upstream.

Current bounded definitive-no-effect status set:

`400, 401, 403, 404, 405, 409, 410, 415, 422, 429`.

Any status not explicitly classified remains fail-closed.

## 5. Recovery branches

### A. Exact provider object is recovered

A trusted recovery scan may resolve object identity only when it is:

- bound to the same provider, action kind and exact target;
- stored in the same authoritative evidence root as the attempt;
- explicitly complete for the recovery query;
- derived from persisted raw scan bytes;
- performed at or after the persisted attempt start;
- evaluated first for exact correlation cardinality;
- contains exactly one provider object carrying the trusted-boundary-minted `attempt_id`;
- provides provider-side `created_at` causal evidence;
- has `created_at >= attempt.started_at` and `created_at <= scan.scanned_at`;
- and that one correlated object has the exact attempted effect fingerprint.

The order matters:

```text
COUNT(objects with correlation_id == attempt_id) MUST equal 1
THEN created_at MUST NOT predate attempt.started_at
THEN effect_sha256 MUST match
```

If the same correlation id appears on two objects, recovery remains ambiguous even if only one object has the expected body.

Successful identity recovery yields:

```text
RECOVERED_EXTERNAL_EFFECT
CREATED_OBJECT_IDENTITY_RECOVERED
ORIGINAL_SUCCESS_RECEIPT = MISSING_OR_INVALID
SYSTEM_COMPLETION = false
AUTOMATIC_RETRY_ALLOWED = false
TERMINAL_PASS = false
NEXT = SEPARATE_INDEPENDENT_EFFECT_VERIFICATION_REQUIRED
```

Recovery never fabricates the missing original provider receipt or attempt-result binding.

### B. Exact identity cannot be recovered unambiguously

Any of these keep the state fail-closed:

- no recovery scan;
- invalid/tampered scan;
- scan stored outside the attempt evidence root;
- scan predates the attempt;
- incomplete scan;
- zero objects carrying the exact correlation id;
- more than one object carrying the exact correlation id;
- correlated object predates the attempt;
- one correlated object with the wrong effect fingerprint;
- matching body/effect without exact attempt correlation;
- wrong target/provider/action;
- invalid or tampered pre-write attempt evidence;
- raw/unbound provider receipt;
- receipt bound to a different attempt;
- ambiguous provider result such as 5xx.

Result:

```text
RECOVERY_REQUIRED
EFFECT_POSSIBLY_CREATED
AUTOMATIC_RETRY_ALLOWED = false
TERMINAL_PASS = false
```

A complete scan with zero matches still does not prove historical non-creation.

## 6. Invariants

### INV-OSE1 — PRE-WRITE AMBIGUITY JOURNAL

Before a non-idempotent mutation enters the provider boundary, Executor must durably bind:

`provider + action_kind + exact target + exact effect fingerprint + trusted-minted unique attempt_id + started_at`.

The attempt id is minted inside the trusted pre-write boundary and atomically reserved in the authoritative evidence root. Reuse of an already-reserved id is rejected, including reuse with identical content.

Directory creation is part of the durability boundary: newly created evidence-directory entries are fsynced before the attempt can be returned to the provider path.

### INV-OSE2 — UNKNOWN POST-WRITE STATE IS NOT SAFE TO RETRY

If a durable pre-write attempt exists but no exact, causally safe result exists:

```text
CLEAN FAILURE CLAIM = FORBIDDEN
AUTOMATIC RETRY = FORBIDDEN
TERMINAL PASS = FORBIDDEN
```

### INV-OSE3 — RECOVERY DOES NOT FABRICATE THE ORIGINAL RECEIPT

A later provider read may recover exact provider object identity. It must not be relabeled as the missing original write receipt or as the missing attempt-result binding.

### INV-OSE4 — EFFECT MATCH IS NOT ATTEMPT BINDING

```text
SAME BODY != SAME ATTEMPT
SAME TARGET != SAME EFFECT INSTANCE
RAW RECEIPT != ATTEMPT-BOUND RECEIPT
ONE MATCH AFTER CORRELATION COLLISION != UNIQUE RECOVERY
CORRELATION STRING WITHOUT CAUSAL TIME BINDING != NEW EFFECT PROOF
```

### INV-OSE5 — ONE ATTEMPT HAS ONE IMMUTABLE RESULT SLOT

One `attempt_id` may have exactly one durable attempt-result binding. An identical re-finalization may be treated idempotently. A different second result must never create an alternate authoritative history.

### INV-OSE6 — RESPONSE RECEIPT != NO-EFFECT PROOF

A provider response can be authoritative evidence of what response was received while remaining insufficient to prove that no external side effect occurred. Unclassified statuses, including 5xx, remain ambiguous.

### INV-OSE7 — ONE AUTHORITATIVE EVIDENCE ROOT

Attempt journal, provider receipt, attempt-result binding, and accepted recovery scan must resolve to one exact durable evidence root. Cross-root substitution is invalid evidence.

## 7. Candidate implementation

`executor/orphaned_side_effect.py` provides:

- `VerifiedExternalEffectAttempt` — proof-bearing pre-write journal record;
- trusted `secrets.token_hex(16)` attempt/correlation minting;
- atomic attempt-id reservation using a deterministic attempt-id path and exclusive creation;
- durable evidence-directory creation with directory-entry fsync;
- `VerifiedAttemptBoundReceipt` — proof-bearing binding between ARP-001 receipt and exact persisted attempt;
- one deterministic immutable result slot per attempt;
- `_persist_provider_result_for_attempt(...)` — finalizer enforcing same-root persistence and single-result semantics;
- bounded provider-result disposition (`SUCCESS / DEFINITIVE_FAILURE / AMBIGUOUS`);
- `VerifiedExternalRecoveryScan` — proof-bearing recovery scan including provider-side `created_at`;
- `_persist_verified_external_recovery_scan(...)` — deterministic synthetic recovery gateway;
- `assess_orphaned_side_effect_recovery(...)` — fail-closed restart/reconciliation assessment.

Caller-created dictionaries, raw ARP receipts, caller-supplied attempt ids, reused attempt ids, conflicting attempt results, cross-root evidence, tampered persisted evidence, truthy-string booleans, duplicate provider object identities, wrong GitHub target identities, pre-existing correlated objects and ambiguous correlation reuse are rejected or remain `RECOVERY_REQUIRED`.

## 8. Correlation boundary

The regression models a durable recovery correlation id carried by provider-side data and recovered by the trusted scan. The id is minted locally immediately before the write and causal recovery also requires provider-side `created_at` not to predate the attempt.

This candidate does **not** claim that the current live GitHub issue-comment API path already supplies a correlation field or idempotency mechanism. GitHub comments do expose timestamps, but production integration must separately establish how the minted correlation nonce is durably carried by or mapped to the provider object.

Without that proof, production crash-window recovery remains `RECOVERY_REQUIRED` and automatic retry remains forbidden.

## 9. Required regression set

OSE-001 must prove at least:

```text
O1  pre-write attempt is durable before provider result handling
O2  attempt id is minted inside the trusted boundary
O3  attempt id reuse in the same authoritative evidence root is rejected atomically
O4  fresh evidence-directory entry is fsynced with its parent before attempt returns
O5  missing exact attempt-bound result => RECOVERY_REQUIRED
O6  provider-result persistence/binding error => recovery-required exception, not clean failure
O7  success receipt from attempt A cannot complete attempt B
O8  failure receipt from attempt A cannot fail attempt B
O9  raw ARP receipt without OSE attempt binding cannot close recovery
O10 one attempt cannot acquire two conflicting durable result bindings
O11 5xx provider response remains AMBIGUOUS / RECOVERY_REQUIRED
O12 exact complete uniquely-correlated causal scan recovers object identity
O13 pre-existing correlated object cannot be recovered as the new attempt
O14 recovered object does not fabricate original success receipt
O15 recovered object alone does not create SYSTEM_COMPLETED or terminal PASS
O16 same effect without attempt correlation is insufficient
O17 incomplete scan cannot resolve
O18 multiple objects carrying the same attempt correlation remain ambiguous before body matching
O19 zero matches do not become clean FAILED
O20 wrong-target scan fails closed
O21 truthy string complete flag is rejected
O22 scan hashes are derived from persisted raw scan bytes
O23 exact effect bytes preserve leading/trailing whitespace and newlines
O24 tampered attempt evidence fails closed
O25 caller cannot mint/replace verified attempt or recovery scan objects
O26 correctly attempt-bound ARP success receipt bypasses recovery normally
O27 result persistence into a different evidence root is rejected
O28 recovery scan from a different evidence root is rejected
```

## 10. Forbidden outcomes

Any of these is a regression failure:

```text
MISSING_ATTEMPT_BOUND_RESULT_AFTER_INFLIGHT_WRITE -> FAILED
MISSING_ATTEMPT_BOUND_RESULT_AFTER_INFLIGHT_WRITE -> RETRY_ALLOWED
RECEIPT_FROM_ATTEMPT_A -> CLOSE_ATTEMPT_B
RAW_ARP_RECEIPT -> CLOSE_ORPHAN_PATH
CALLER_SUPPLIED_ATTEMPT_ID -> TRUSTED_CORRELATION
REUSED_ATTEMPT_ID -> NEW_WRITE_ALLOWED
ONE_ATTEMPT -> TWO_DIFFERENT_RESULT_BINDINGS
HTTP_5XX -> DEFINITIVE_NO_EFFECT_FAILURE
PREEXISTING_CORRELATED_OBJECT -> RECOVERED_AS_NEW_ATTEMPT
CROSS_ROOT_RESULT_OR_SCAN -> ACCEPTED
CORRELATION_ID_ON_MULTIPLE_OBJECTS -> RECOVERED
ZERO_RECOVERY_MATCHES -> PROOF_NOT_CREATED
SAME_BODY_WITHOUT_CORRELATION -> RECOVERED
INCOMPLETE_SCAN -> RECOVERED
RECOVERY_SCAN -> FABRICATED_ORIGINAL_SUCCESS_RECEIPT
RECOVERED_IDENTITY -> TERMINAL_PASS
TAMPERED_ATTEMPT -> RETRY_ALLOWED
```

## 11. Relationship to ARP-001

ARP-001 establishes whether a provider receipt is authoritative evidence for a provider response and external object identity.

OSE-001 adds stricter questions:

> Is that receipt durably bound to this exact pre-write attempt?
>
> Is the provider result causally sufficient to prove success or a definitive no-effect failure?
>
> Is there exactly one durable result history for this attempt?

Therefore:

```text
ARP RECEIPT AUTHORITY != OSE ATTEMPT/RESULT PROVENANCE
ARP FAILURE RESPONSE != OSE DEFINITIVE NO-EFFECT FAILURE
```

## 12. Scope / non-claims

This candidate does not:

- modify PR #83;
- add a live GitHub mutation adapter;
- execute any external provider write;
- retry any historical action;
- close FAI-009 for all providers;
- claim current GitHub comment recovery correlation exists;
- enable automatic retries;
- change merge/release/deploy/tag authority;
- activate P5 or a new product-development phase.

## 13. Acceptance boundary

This stacked candidate can be considered technically ready for Human review only when:

```text
- all OSE-001 deterministic/adversarial regressions pass;
- all inherited ARP-001 tests remain green;
- full Executor foundation suite passes on the exact stacked head;
- GP001 replay repeatability passes on the exact stacked head, or the Human explicitly changes that acceptance requirement;
- no live provider mutation is required;
- PR remains draft/unmerged until separate Human action;
- no claim is made that production GitHub recovery is wired.
```
