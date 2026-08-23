---
document: "INC-001 Orphaned External Effect"
status: "OBSERVED / UNVERIFIED EXTERNAL EFFECT"
date: "2026-08-23"
repository: "JTJ07/Executor"
external_target: "eclipse-jdtls/eclipse.jdt.ls#3866"
---

# INC-001 — Orphaned External Effect / Authoritative Receipt Unavailable

## 1. Why this record exists

A real implementation session reported that an evidence update had been published as a GitHub issue comment and then performed a live verification. The verification could not find the new comment and asked the human user to provide the comment permalink.

This record freezes the failure before any human repair or retry can make the original execution path look successful.

## 2. Preserved observations

External target:

`eclipse-jdtls/eclipse.jdt.ls#3866`

Independent live read performed on 2026-08-23 found:

- issue state: `open`;
- issue `comments`: `4`;
- issue `updated_at`: `2026-08-14T17:43:04Z`;
- the issue comments endpoint exposed only the same four pre-existing comments;
- the last visible comment remained `usrlocl` comment id `5296398438`;
- no newly created evidence-update comment object was available for binding.

Provider endpoints used for the independent observation:

- `https://api.github.com/repos/eclipse-jdtls/eclipse.jdt.ls/issues/3866`
- `https://api.github.com/repos/eclipse-jdtls/eclipse.jdt.ls/issues/3866/comments`

No duplicate publication was attempted during this investigation.
No human-supplied permalink was used to repair the execution record.

## 3. What is known and what is not known

### Known

- a completion/publication claim existed in the implementation-session narrative;
- the later verification path did not possess an authoritative provider object identity for that claimed write;
- independent readback did not expose the claimed new object;
- the system therefore could not prove the claimed external effect from its own retained evidence.

### Unknown

The original raw write-tool response is not available in this verification context. Therefore this incident does **not** prove which of these two mechanisms occurred:

A. GitHub returned a valid creation receipt, but the execution path failed to persist or retain it for verification; or

B. no valid creation receipt was ever obtained, but the action was nevertheless described as published/completed.

The current evidence must not choose between A and B without the original tool response.

## 4. Evidence verdict

```text
ACTION CLAIMED:               YES
AUTHORITATIVE WRITE RECEIPT: UNAVAILABLE TO VERIFICATION PATH
PROVIDER OBJECT ID:           UNAVAILABLE
PROVIDER OBJECT URL:          UNAVAILABLE
INDEPENDENT READBACK:         CLAIMED OBJECT NOT FOUND
HUMAN RECOVERY:               NOT USED
RETRY / REPUBLISH:            NOT PERFORMED
TERMINAL PASS:                FORBIDDEN
STATE:                        UNVERIFIED_EXTERNAL_EFFECT
```

The absence of the comment during readback must not be rewritten as proof that the write definitely never occurred. The correct claim is narrower: **the external effect is not provable from the retained authoritative evidence**.

## 5. Failure classification

Primary failure class:

`FAI-008 — ORPHANED EXTERNAL EFFECT / RECEIPT LOSS`

Failure boundary:

```text
AUTHORIZED / REQUESTED EXTERNAL MUTATION
  -> MUTATION ATTEMPT
  -> COMPLETION CLAIM
  -> AUTHORITATIVE PROVIDER RECEIPT NOT AVAILABLE
  -> LATER READBACK CANNOT BIND TO THE CREATED OBJECT
  -> HUMAN ASKED TO RECONSTRUCT OBJECT IDENTITY
```

This is an action-result binding failure at the provider-effect boundary, not merely a readback inconvenience.

## 6. Invariant derived from the incident

`EXTERNAL MUTATION COMPLETION REQUIRES AN AUTHORITATIVE PROVIDER RECEIPT.`

Operational form:

```text
WRITE
  -> CAPTURE PROVIDER RESPONSE
  -> PERSIST OBJECT IDENTITY + RESPONSE HASH
  -> ONLY THEN CLAIM COMPLETION
  -> INDEPENDENT READBACK
  -> VERIFICATION
```

If the provider receipt is missing or invalid:

```text
NO RECEIPT
  -> UNVERIFIED_EXTERNAL_EFFECT
  -> NO TERMINAL SUCCESS
  -> NO AUTOMATIC RETRY WHILE EFFECT IS UNCERTAIN
```

A permalink supplied later by the human may support a separate human investigation, but it must not retroactively convert the original automated path into a receipt-complete execution.

## 7. Regression requirement

A deterministic regression must prove all of the following:

1. a completion/PASS claim without an authoritative provider receipt becomes `UNVERIFIED_EXTERNAL_EFFECT`;
2. a human-supplied object URL without the original provider response evidence is insufficient;
3. a receipt bound to the wrong target is rejected;
4. a valid provider receipt is still not terminal proof — it advances only to `RECEIPT_BOUND_VERIFICATION_REQUIRED`;
5. independent readback remains a separate verification boundary.

## 8. Scope statement

This incident record does not claim that the current Executor runtime already routes every external provider mutation through the new receipt gate. It records the real failure, defines the missing boundary, and provides a falsifiable regression target. Adapter/runtime integration must be claimed only where the gate is actually wired into the mutating path.
