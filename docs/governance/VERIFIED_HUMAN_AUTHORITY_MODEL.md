---
document: "Verified Human Authority Model"
version: "0.2"
status: "DIRECTION ACCEPTED / DRAFT PENDING MERGE"
date: "2026-08-09"
scope: "evidence, identity and bounded-authorization requirements for human authorization of an exact contract"
repository: "litrgratis-pixel/Executor"
---

# Verified Human Authority Model v0.2

## 1. Purpose

This document defines what Executor must mean when it claims that a human authorized a contract.

It does not implement authentication, UI, signatures, identity providers, buttons, sessions or executable contract freezing.

The core rule is:

> **A HUMAN DECISION IS AUTHORITY ONLY WHEN EXTERNAL EVIDENCE BINDS A VERIFIED ACTOR, AN EXACT DECISION AND THE EXACT CONTRACT IDENTITY THAT ACTOR REVIEWED.**

The formation layer may prepare review material and request a decision. It may not prove its own human authorization.

A second governing rule is equally important:

> **HUMAN AUTHORITY IS A BOUNDED AUTHORIZATION, NOT A GENERAL DELEGATION.**

A human approval authorizes only the exact decision request and exact contract identity to which the verified decision is bound. It does not create standing trust for later contracts or unrelated actions.

## 2. Why this boundary exists

PR #50 closed F-4 by removing a process-local path that could self-declare human authority.

Rejected pattern:

```text
caller
  |
  v
HumanDecisionReceipt(
  authority_source = "HUMAN_AUTHORITY"
)
  |
  v
AUTHORIZED_AND_FROZEN
```

This fails because a caller-controlled label is not evidence that a human made a decision.

Therefore:

```text
SELF-DECLARED HUMAN AUTHORITY
        !=
VERIFIED HUMAN AUTHORITY
```

The next problem is not "how to add an approval button".

The problem is:

> How can Executor establish that a verified human actor approved exactly the immutable contract identity that will later be frozen for execution, and only that contract identity?

## 3. Distinct objects

The following objects must remain separate:

```text
DRAFT CONTRACT
      !=
DECISION REQUEST
      !=
HUMAN REVIEW MATERIAL
      !=
HUMAN ACTION
      !=
VERIFIED DECISION RECEIPT
      !=
AUTHORIZED / FROZEN CONTRACT
```

### Draft Contract

A non-executable contract proposal produced by the formation layer.

It has an immutable canonical identity, minimally:

```text
draft_contract_sha256
```

### Decision Request

A non-executable request asking a superior human-authority boundary for one of the allowed decisions:

```text
ACCEPT
MODIFY
REJECT
```

The request must bind to the exact draft identity and the exact review material that is intended to be shown.

### Human Review Material

The material presented for human judgment.

It must be sufficient for the human to understand the proposed authority boundary, including at least:

```text
original user request
understood objective
repository / input identity
proposed write scope
protected material
success conditions
discovered but out-of-scope work
unresolved assumptions
critical critique findings
exact draft contract hash
```

A hash alone is not useful review material. A readable summary without an exact immutable binding is not sufficient authority evidence.

The review material therefore needs both:

```text
human-readable meaning
+
machine-verifiable identity
```

### Human Action

An externally observed action by a verified human actor in response to a specific decision request.

A generic event such as:

```text
user_clicked_button = true
```

is not sufficient by itself.

The system must know what exact decision request the action answered and what exact material was bound to that request.

### Verified Decision Receipt

Evidence produced or verified by a superior trust boundary outside the formation caller.

It records that a verified actor made one explicit decision about one exact reviewed contract identity.

The formation layer may consume a verified receipt. It may not mint one merely by constructing an object in process memory.

### Authorized / Frozen Contract

The executable contract identity created only after the verified receipt has been validated against the exact current draft.

The authorized contract must be canonical-identity equivalent to the contract identity approved by the human.

## 4. Minimal authority chain

```text
DRAFT CONTRACT
      |
      v
DECISION REQUEST
      |
      v
HUMAN REVIEW MATERIAL
      |
      v
VERIFIED HUMAN ACTION
      |
      v
VERIFIED DECISION RECEIPT
      |
      v
EXACT-IDENTITY CHECK
      |
      v
AUTHORIZED / FROZEN CONTRACT
```

No transition in this chain may be replaced by a model assertion.

## 5. Required receipt semantics

The exact serialization format is intentionally not frozen here, but any future receipt must establish at least the following facts:

```text
decision_request_id
actor_identity
authority_evidence_ref
decision
reviewed_contract_sha256
review_material_sha256
decision_request_sha256
decision_time
freshness / replay identity
```

A future implementation may add a nonce, challenge, signature, session binding or external identity-provider evidence. Those mechanisms are implementation choices.

The governance requirement is the property they must prove, not a specific authentication technology.

## 6. Actor identity rule

The statement:

```text
actor = USER
```

is not proof.

The receipt must refer to evidence that an external trust boundary has already verified for the actor identity relevant to the decision.

This follows the same general authority pattern already used elsewhere in Executor:

```text
CLAIMED ROLE
    !=
VERIFIED ROLE / IDENTITY EVIDENCE
```

The formation kernel must not be able to add itself to the trusted actor set.

Authentication proves approximately who the actor is. It does not prove what that actor authorized.

## 7. Exact contract identity rule

The central invariant is:

> **AUTHORIZATION MUST BIND TO EXACT CONTRACT IDENTITY.**

Required equality before freeze:

```text
verified_receipt.reviewed_contract_sha256
        ==
current_draft_contract_sha256
        ==
contract_sha256_to_be_frozen
```

If any value differs:

```text
AUTHORIZED_AND_FROZEN = FORBIDDEN
```

Human approval of one contract never transfers automatically to a later modified contract.

## 8. Bounded authorization rule

Human authority is not a standing capability grant.

Correct meaning:

```text
VERIFIED HUMAN ACTOR
  authorizes
DECISION D
  for
DECISION REQUEST R
  covering
EXACT CONTRACT C
  reviewed through
EXACT MATERIAL M
```

Incorrect meaning:

```text
VERIFIED HUMAN ACTOR
  once approved something
      -> Executor is now generally trusted
      -> future contracts/actions inherit approval
```

Therefore:

```text
ONE APPROVAL
    !=
GENERAL DELEGATION
```

and:

```text
AUTHORIZATION EVENT A
    !=
AUTHORITY FOR FUTURE CONTRACTS B, C, D
```

A future delegation model, if ever introduced, must be a separate explicit governance object with its own scope, duration, revocation, actor and capability semantics. It must never be inferred from a normal contract approval.

## 9. F-4 retained — Self-Declared Decision Authority

Failure mechanism:

```text
caller creates object saying "human approved"
      -> formation accepts object as proof
      -> contract freezes
```

Invariant:

```text
SELF-DECLARED DECISION AUTHORITY
        !=
VERIFIED HUMAN AUTHORITY
```

Required behavior:

- caller-created role labels do not authorize;
- caller-created evidence references do not authorize unless independently verified;
- process-local construction cannot mint a trusted receipt;
- formation remains fail-closed when superior evidence is absent.

## 10. F-5 — Approval Drift

Failure mechanism:

```text
DRAFT A
  |
  v
HUMAN REVIEWS A
  |
  v
HUMAN ACCEPTS A
  |
  v
SYSTEM CHANGES A -> B
  |
  v
OLD APPROVAL REUSED
  |
  v
B EXECUTED
```

This is a real authority failure even if:

- the human actor was authentic;
- the human genuinely chose ACCEPT;
- the original approval evidence is valid.

The failure is identity drift: the verified decision does not authorize the executed contract.

Invariant:

```text
HUMAN APPROVAL OF CONTRACT A
        !=
HUMAN APPROVAL OF CONTRACT B
```

Required behavior:

```text
any semantic or canonical draft change
      -> new contract hash
      -> previous ACCEPT becomes stale for freeze
      -> new review / authorization required
```

## 11. F-6 — Authorization Generalization / Delegation Drift

Failure mechanism:

```text
HUMAN APPROVES CONTRACT A
      |
      v
SYSTEM RECORDS "USER TRUSTS EXECUTOR"
      |
      v
LATER CONTRACT B OR ACTION Y
      |
      v
OLD APPROVAL TREATED AS STANDING AUTHORITY
      |
      v
B / Y EXECUTED WITHOUT NEW BOUNDED AUTHORIZATION
```

This differs from F-5.

F-5 changes the identity of the contract after a valid approval.

F-6 keeps the original approval valid for A but improperly generalizes it into authority for some other contract or action.

Invariant:

```text
HUMAN AUTHORITY IS BOUNDED AUTHORIZATION,
NOT GENERAL DELEGATION
```

Required behavior:

```text
receipt for request R / contract C
      can authorize only R / C
```

Any attempt to use the receipt as a capability token for another contract, another decision request or unrelated future work must fail closed.

## 12. Required adversarial cases

The future boundary must be attacked at least with these cases.

### Actor mismatch

```text
receipt actor != externally verified actor binding
```

Expected result: reject.

### Contract mismatch

```text
reviewed_contract_sha256 != current contract sha256
```

Expected result: reject.

### Review-material mismatch

The human action refers to review material whose hash does not match the material bound into the decision request.

Expected result: reject.

### Stale approval after modification

Draft changes after ACCEPT.

Expected result: old receipt cannot freeze the new draft.

### Receipt replay

A receipt valid for one decision request is reused for another request or later contract instance.

Expected result: reject unless the identities are provably the same authorization event and same exact contract identity.

### Generalized approval

A valid receipt for contract A is presented as evidence that the actor generally trusts Executor or authorizes contract B.

Expected result: reject.

### Fabricated decision event

Caller provides a syntactically valid receipt-like object without verified external authority evidence.

Expected result: reject.

### Decision substitution

Human chose `REJECT` or `MODIFY`, but a downstream component substitutes `ACCEPT`.

Expected result: authoritative evidence binding must expose the mismatch; freeze is forbidden.

### Incomplete review material

The human is asked to approve without being shown material necessary to understand the authority boundary, while the receipt still claims full approval.

Expected result: the mechanism must not treat this as proof of informed approval of omitted scope.

The exact completeness policy belongs to the future implementation contract, but the omission must not be invisible.

## 13. What a verified decision proves

A valid verified decision receipt may prove only:

```text
A verified human actor
made decision D
for exact decision request R
about exact reviewed contract C
using exact bound review material M
at decision event/time T.
```

It does not prove:

- that the contract is technically correct;
- that execution will succeed;
- that the contract is safe under all policies;
- that the user request was perfectly interpreted;
- that later modified contracts are authorized;
- that different contracts are authorized;
- that Executor has standing delegated authority;
- that execution evidence is valid;
- that product acceptance has occurred.

Therefore:

```text
VERIFIED HUMAN AUTHORITY != TECHNICAL CORRECTNESS
VERIFIED HUMAN AUTHORITY != EXECUTION SUCCESS
VERIFIED HUMAN AUTHORITY != PROOF OF RESULT
VERIFIED HUMAN AUTHORITY != GENERAL DELEGATION
```

## 14. Authority versus authentication

Authentication answers approximately:

> Who is this actor?

Authorization evidence answers:

> What exact decision did this verified actor make about what exact contract identity?

Executor requires both properties across the full boundary.

An authenticated session alone does not authorize an arbitrary contract.

A contract hash alone does not prove a human approved it.

A previous valid approval does not create standing permission for future contracts.

## 15. Required future implementation boundary

The next implementation must create a component or adapter whose authority does not originate from the formation caller.

Conceptually:

```text
FORMATION KERNEL
  emits Decision Request
        |
        v
EXTERNAL / SUPERIOR HUMAN AUTHORITY BOUNDARY
  authenticates actor
  presents bound review material
  records explicit decision
  verifies decision/request/material bindings
  emits Verified Decision Receipt
        |
        v
FORMATION FREEZE GATE
  verifies receipt
  verifies exact current contract identity
  verifies receipt is bounded to this request/contract
  freezes only exact approved contract
```

The same process may host some of these operations in an early implementation only if the authority evidence itself cannot be forged by the untrusted/caller-controlled portion and the trust ownership remains explicit.

## 16. Implementation non-goals

This governance model does not yet choose:

- web UI;
- CLI prompt;
- GitHub approval;
- hardware key;
- OAuth/OIDC provider;
- passkey;
- digital-signature format;
- database;
- ledger;
- receipt transport;
- multi-user organization model;
- delegation implementation;
- quorum approval;
- automatic approval.

Those choices are premature until the authority semantics are accepted.

## 17. Minimal authorization receipt design — next design problem

The next design step must define the smallest receipt contract capable of proving the model above without selecting a full UI or identity platform.

At minimum it must answer:

```text
WHO produced the decision?
WHAT decision was made?
WHICH decision request was answered?
WHICH exact contract identity was reviewed?
WHICH exact review material was shown?
WHEN / under which freshness identity did it occur?
WHY can the formation caller not forge this evidence?
WHY can the receipt not authorize any other contract?
```

The design must remain non-executable until those properties have adversarial tests.

## 18. Acceptance conditions for the model

This document is sufficient as the governance baseline only if it makes the following statements unambiguous:

```text
HUMAN ACTION != VERIFIED HUMAN AUTHORITY
AUTHENTICATED ACTOR != AUTHORIZATION OF ARBITRARY CONTRACT
APPROVAL OF A != APPROVAL OF B
AUTHORIZATION MUST BIND TO EXACT CONTRACT IDENTITY
HUMAN AUTHORITY IS BOUNDED AUTHORIZATION, NOT GENERAL DELEGATION
FORMATION CANNOT MINT ITS OWN HUMAN AUTHORITY
VERIFIED HUMAN AUTHORITY != TECHNICAL PROOF
```

PR #51 remains a draft until a separate user decision authorizes merge. Direction acceptance is not merge authorization.

Only after this model is accepted for merge should Executor implement the first minimal verified-human-authority boundary contract.
