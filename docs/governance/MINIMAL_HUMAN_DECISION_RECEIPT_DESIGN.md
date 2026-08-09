---
document: "Minimal Human Decision Receipt Design"
version: "0.2"
status: "ADVERSARIAL DESIGN REVIEW / IMPLEMENTATION BLOCKED"
date: "2026-08-09"
scope: "human decision record, external authority evidence, exact freeze verification"
repository: "litrgratis-pixel/Executor"
---

# Minimal Human Decision Receipt Design v0.2

```text
HUMAN DECISION RECEIPT != VERIFIED AUTHORITY EVIDENCE
VERIFIED AUTHORITY EVIDENCE != AUTHORIZED CONTRACT
AUTHENTICATION != AUTHORIZATION
AUTHORIZATION != DELEGATION
```

## Boundary

```text
FORMATION KERNEL
  creates exact draft + review + decision request
        ↓
HUMAN DECISION ADAPTER
  records human action; DOES NOT prove authority
        ↓
HUMAN DECISION RECEIPT
  records WHO / WHAT / exact bound identities
        ↓
EXTERNAL AUTHORITY EVIDENCE
  proves actor + authority context independently
        ↓
FREEZE GATE
  verifies evidence + current exact identities
        ↓
AUTHORIZED_AND_FROZEN
```

No component may silently combine decision capture, authority proof, contract mutation, and freeze.

## Human Decision Receipt

The receipt is a record, not a permission system.

Minimum semantic fields:

```text
schema_version
receipt_id
decision_request_id
decision_request_sha256
actor_subject
authority_evidence_ref
decision: ACCEPT | MODIFY | REJECT
reviewed_contract_sha256
review_material_sha256
formation_profile_sha256
canonical_task_sha256
executor_commit
decision_event_id
observed_at
freshness_id
```

It deliberately does not define `permissions`, `roles`, `allowed_actions`, `general_trust`, or `delegated_capabilities`.

It records the decision fact and points to external authority evidence. It does not itself explain why the actor had authority.

## External authority evidence

```text
DECISION FACT != AUTHORITY TO MAKE THAT DECISION
```

The evidence referenced by `authority_evidence_ref` must be independently verifiable and establish at least:

```text
verified actor subject
verified issuer / trust owner
verified authority context
binding to the relevant decision event or decision request
freshness / validity required by the chosen mechanism
```

Authority semantics live in that external boundary, not in caller-controlled receipt fields.

## F-7 — Authority Substitution

```text
HUMAN A approves contract C
        ↓
system verifies only "some authenticated human approved"
        ↓
Human B / wrong account / wrong authority context
is treated as equivalent
        ↓
freeze
```

```text
F-4: no verified human decision exists
F-5: approval reused after contract identity changes
F-6: bounded approval generalized to another contract/action
F-7: wrong actor or authority context substituted as equivalent
```

Invariant:

```text
"SOME HUMAN APPROVED" != "THE REQUIRED AUTHORITY APPROVED"
AUTHORITY IDENTITY MUST BIND TO EXACT DECISION CONTEXT
```

## Exact freeze rule

Only `ACCEPT` may be freeze-eligible.

Future freeze requires:

```text
receipt.decision == ACCEPT
external authority evidence independently valid
verified actor subject == receipt.actor_subject
verified authority context == required authority context
receipt.decision_request_sha256 == current decision_request_sha256
receipt.reviewed_contract_sha256 == current draft hash == frozen contract hash
receipt.review_material_sha256 == current review-material hash
receipt.formation_profile_sha256 == current formation-profile hash
receipt.canonical_task_sha256 == current canonical-task hash
receipt.executor_commit == current exact Executor formation commit
```

Boundedness does not come from a self-declared `SINGLE_CONTRACT=true` field. It comes from exact verifier acceptance for one request/contract identity.

Any mismatch:

```text
AUTHORIZED_AND_FROZEN = FORBIDDEN
```

## Decision semantics

`ACCEPT` proceeds only to exact authority + identity verification.

`MODIFY` requires a new draft, hash, critique, review material, decision request, and human decision.

`REJECT` never authorizes.

## Replay

No global one-time-use receipt ledger is introduced.

```text
same receipt + different request/contract/review identity = INVALID
same receipt + same immutable identities + same verified authority context = same authorization fact
```

Same-identity revalidation is idempotent verification, not new or broader authority.

## Adversarial cases required before implementation

At minimum test:

1. caller-forged receipt;
2. fabricated authority evidence reference;
3. authenticated actor without authority for this context;
4. Human A receipt paired with Human B evidence;
5. correct subject under wrong account/organization context;
6. wrong contract/request/review hashes;
7. stale approval after A -> B;
8. receipt reused across another contract/request;
9. old approval treated as standing trust;
10. `REJECT` -> `ACCEPT` substitution;
11. `MODIFY` used to execute without re-review;
12. authority issuer/context mismatch;
13. missing/unverifiable authority evidence;
14. decision adapter certifies its own evidence;
15. formation kernel acts as evidence verifier;
16. review material changes after human action;
17. receipt self-declared permissions influence verifier;
18. valid login/session without exact decision binding.

Unauthorized result:

```text
FAIL CLOSED
NO FROZEN CONTRACT
NO EXECUTION AUTHORITY
```

## Current adversarial-review findings

```text
R-1 Human Authorization Receipt was too strong
    -> Human Decision Receipt
R-2 adapter role was too broad
    -> split decision capture from authority evidence
R-3 receipt self-described bounded authority
    -> boundedness moved to freeze-gate exact identity semantics
R-4 authority substitution was implicit
    -> F-7 made explicit
```

F-7 should also be reflected in PR #51 before #51 is ever merged.

## Next question

Implementation remains blocked.

> Can the freeze gate verify external authority evidence without becoming a second permission system or trusting a caller-selected authority context?
