---
document: "Executor Phase B Human Semantic Authorization"
status: "ACTIVE / HUMAN DECISION"
date: "2026-08-16"
target_repository: "JTJ07/Executor"
base_sha: "5e254811023553d1abe8bdbb3535b8150aaf19ad"
completion_map: "PROJECT_COMPLETION_MAP.md"
---

# PHASE B AUTHORIZATION

This file records the human decision that activates Phase B. It does not prove implementation, pilots, P4 completion, release, deployment or final acceptance.

## Selected semantic forks

```text
RECOVERED EXECUTOR GOAL: ACCEPT
HR-1: C — P4 REPEATABLE EXECUTOR 1.0
HR-2: A — EXTERNAL GOVERNED REQUEST INTAKE
HR-3: A — GITHUB
HR-4: A — EXTERNAL INTELLIGENCE
HR-5: C — BOUNDED REAL PILOT CLASS
```

GitHub is the first concrete trust domain. Each request and human `ACCEPT / MODIFY / REJECT` must bind an authenticated GitHub actor, immutable event identity, exact content hashes and the exact current draft hash. Replay, changed content, wrong actor, draft mismatch, expiry or missing evidence fail closed. This does not authorize generalized IAM.

The only pilot repositories are `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`. At least one real, objectively verifiable quality/correctness fix is required in each. Each pilot may touch at most 1–3 production files plus necessary test/evidence files.

Allowed external effects are a dedicated branch, commits and a draft pull request. Merge, deploy, release, new secrets, new credentials and new paid services are forbidden. External Intelligence owns solution proposals; Executor owns effect governance and evidence.

Implementation choices and routing are delegated. Phase B continues until every selected gate passes or an objective external blocker occurs. The executing agent cannot supply independent Phase C PASS or final human acceptance.
