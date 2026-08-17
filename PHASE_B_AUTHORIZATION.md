---
document: "Executor Phase B Human Semantic Authorization"
status: "ACTIVE / HUMAN DECISION"
date: "2026-08-17"
target_repository: "JTJ07/Executor"
base_sha: "5e254811023553d1abe8bdbb3535b8150aaf19ad"
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

Allowed external effects are a dedicated branch, commits and a draft pull request. Merge, deploy, release, new secrets, new credentials and new paid services are forbidden. External Intelligence owns solution proposals; Executor owns effect governance and evidence.

Implementation choices and routing are delegated. Phase B continues until every selected gate passes or an objective external blocker occurs. The executing agent cannot supply independent Phase C PASS or final human acceptance.

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
