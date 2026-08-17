---
document: "Executor Phase B Human Semantic Authorization"
status: "ACTIVE / HUMAN DECISION"
date: "2026-08-18"
target_repository: "JTJ07/Executor"
completion_map: "PROJECT_COMPLETION_MAP.md"
---

# PHASE B AUTHORIZATION

This file records the human decisions that activate and constrain Phase B. It does not prove implementation, pilots, P4 completion, release, deployment or final acceptance.

## Selected semantic forks

```text
RECOVERED EXECUTOR GOAL: ACCEPT
HR-1: C — P4 REPEATABLE EXECUTOR 1.0
HR-2: A — EXTERNAL GOVERNED REQUEST INTAKE
HR-3: A — GITHUB
HR-4: A — EXTERNAL INTELLIGENCE
HR-5: C — BOUNDED REAL PILOT CLASS
```

GitHub is the first concrete trust domain. Each request and human `ACCEPT / MODIFY / REJECT` must bind an authenticated GitHub actor, immutable event identity, exact content hashes and the exact current draft hash. Replay, changed content, wrong actor, draft mismatch, expiry or missing evidence fail closed according to the revocation cutoff below. This does not authorize generalized IAM.

The only pilot repositories are `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`. At least one real, objectively verifiable quality/correctness fix is required in each. Each pilot may touch at most 1–3 production files plus necessary test/evidence files.

Allowed external effects are a dedicated branch, commits and a draft pull request. Merge, deploy, release, new secrets, new credentials and new paid services are forbidden unless separately authorized. External Intelligence owns solution proposals; Executor owns effect governance and evidence.

Implementation choices and routing are delegated. The executing agent cannot supply independent Phase C PASS or final human acceptance.

## Authority revocation cutoff — HUMAN DECISION

Accepted by the human on 2026-08-17, verbatim:

```text
AKCEPTUJĘ REVOCATION CUTOFF AT GLOBAL CONTRACT_ACCEPT CONSUMPTION
AKCEPTUJĘ FINAL LIVE VERIFICATION AS REVOCATION CUTOFF BOUND INTO SUCCESSFUL GLOBAL CONTRACT_ACCEPT CONSUMPTION
```

Normative meaning:

1. A direct-human GitHub request/decision remains revocable while it is a mutable provider event and before the final live provider verification used for `CONTRACT_ACCEPT`.
2. Immediately before global `CONTRACT_ACCEPT` consumption, Executor must re-fetch and verify the exact request and exact decision with the authoritative GitHub trust verifiers. Edit, deletion, mismatch, expiry, wrong actor/origin or other failed current-provider verification blocks before freeze.
3. That final verification produces one exact immutable authority snapshot binding request/decision provider identity, content hashes, immutable event IDs, exact request and draft bindings, direct-human provenance, freshness/expiry, decision edit state and the pinned target commit/tree evidence.
4. The snapshot becomes authority only if that exact snapshot hash is successfully consumed in the global one-shot `CONTRACT_ACCEPT` namespace and the resulting frozen decision/result is durably bound. Failed global consumption creates no `AUTHORIZED_AND_FROZEN` authority; any retry requires a new final live provider verification and may not reuse the failed verification snapshot as dormant authority.
5. Once successful `CONTRACT_ACCEPT` consumption creates `AUTHORIZED_AND_FROZEN`, the consumed snapshot is the immutable authority source. A later edit/deletion of the original GitHub request or ACCEPT comment is historical provider mutation and does not retroactively revoke or rewrite that frozen contract.
6. `CONTRACT_ACCEPT` authority is not consequential-effect authority. Execution still requires the exact frozen contract, bounded proposal, policy, AAP/effect authority, global one-shot effect reservation, effect-side `not_after`/provider-time checks, local atomic consumption, scope/isolation controls and terminal evidence/result binding.
7. Post-cutoff execution must not silently restore mutable GitHub issue/comment currentness as a second revocation mechanism.

No cross-resource atomic transaction between GitHub Issue/Comment state and Git refs is claimed. The accepted linearization semantics are: **FINAL LIVE VERIFIED SNAPSHOT + SUCCESSFUL GLOBAL CONTRACT_ACCEPT CONSUMPTION**.

## Final acceptance gate reconciliation — HUMAN DECISION

Accepted by the human on 2026-08-18, verbatim:

```text
AKCEPTUJĘ FINAL ACCEPTANCE GATE RECONCILIATION
```

This is a narrow governance reconciliation. It does not change the selected P4 goal, the evidence burden, Executor implementation semantics, the exact candidate identity, or any technical gate. It removes only the circular dependency between G-15, G-17 and G-18.

Normative meaning:

```text
G-15 = TECHNICAL / PRODUCT-VALUE ENDPOINT COMPLETION
G-17 = FRESH INDEPENDENT TECHNICAL PHASE-C VERDICT
G-18 = EXCLUSIVE FINAL HUMAN ACCEPTANCE
```

### G-15

G-15 includes all technical, product-value, repeatability, metric and operational requirements of the selected P4 endpoint, **excluding final Human product acceptance**.

The phrase:

```text
EXECUTOR 1.0: ACCEPT
```

is not a prerequisite for G-15 PASS.

### G-17

G-17 PASS means that a fresh independent Phase-C verifier has established that G-01 through G-17 are technically/evidentially satisfied and that no active FALSE SUCCESS path remains.

A valid technical terminal state before Human final acceptance is therefore:

```text
TECHNICAL / PHASE-C EVIDENCE: PASS
G-01–G-17: PASS
PROJECT COMPLETION: BLOCKED ONLY ON G-18
```

### G-18

G-18 is the exclusive owner of the final Human product-acceptance decision:

```text
EXECUTOR 1.0: ACCEPT
```

Only the Human may establish G-18 PASS.

Release/tag remains a separate Human-authorized decision and is not automatically authorized by G-18.

### Required order

```text
G-01–G-16
  -> FRESH INDEPENDENT PHASE C / G-17
  -> FINAL HUMAN ACCEPTANCE / G-18
  -> PROJECT COMPLETE
```

### Narrow precedence rule

This later explicit Human decision supersedes only conflicting wording in earlier completion-map text that made `EXECUTOR 1.0: ACCEPT` simultaneously a prerequisite of G-15 and the separate G-18 gate, or otherwise required final Human acceptance before G-17 could pass.

All other requirements of `PROJECT_COMPLETION_MAP.md`, including P4 technical/product evidence, FALSE SUCCESS = 0, independent verification and Human ownership of final acceptance, remain unchanged.

For the exact implementation candidate `f60829f90ea2f69dc501582daf109b59676be07e`, this governance reconciliation does not mutate the candidate and does not invalidate its exact-head technical evidence. It changes only the interpretation/order of the final governance gates.