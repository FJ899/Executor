# P1 Evidence Protocol

Status: **PROPOSED — MUST BE FROZEN BEFORE THE FIRST AUTHORITATIVE DISPATCH**  
Protocol ID: `P1-EVIDENCE-PROTOCOL-001`  
Prepared: `2026-08-04`  
Product state at preparation: `EXECUTOR CODE ACCEPTED / BOOTSTRAP COMPLETE / PROOF PENDING / P1 NOT CLAIMED`

## 1. Objective

The P1 proof asks one bounded question:

> Can Executor perform an authorized, limited operation in a way that gives the system sufficient independent evidence to say: **we know what happened**?

The protocol must establish that Executor:

- performs only the authorized operation against the authorized source and exact candidate revision;
- cannot be persuaded by candidate-controlled tests, reports, environment, Docker authority, acquisition state, or declared results to emit a false terminal PASS;
- produces complete, integrity-bound evidence that can be independently replayed without relying on process memory;
- preserves `UNKNOWN`, `NOT RUN`, missing evidence, and failed evidence as states distinct from `PASS`.

This protocol does **not** attempt to prove autonomy, multi-agent operation, general usefulness, ScriptOps readiness, Ginseng readiness, or P2/P3 product value.

## 2. Frozen proof identity

### 2.1 Installed controller baseline

```text
bootstrap PR:        #40
bootstrap merge:     21fdc54c773b987592be309467dff4ec48d7b279
accepted source tree: e54ebdc44c60f76d95b844d0811c009e8916ba44
implementation review: PR #32 / CODE ACCEPT
```

### 2.2 Trusted proof-material blobs

The authoritative run must record its actual `github.workflow_sha` and prove that the following four files are byte-identical to the accepted proof material:

```text
.github/workflows/manual-exact-ref-verify.yml
  git blob: a0abfec3d932bf7522dea033da13172e3ecd6bbc

tools/p1_verifier/verify_candidate.py
  git blob: f216997df4a87d55b09cd29edaf37a84718e81aa

tools/p1_verifier/acceptance_manifest.json
  git blob: 867aa347d666e6c05387746bc8fb26cdc273ca27

tests/test_p1_verifier.py
  git blob: 7fd3fb2767b1706a48257c40a6f10e805a52b000
```

A later documentation-only commit on `main` is permitted only if these four blob identities remain unchanged. A changed trusted blob requires a new review and a new protocol version before any authoritative run.

### 2.3 Frozen candidate inputs

Both required dispatches must use exactly:

```text
target_ref:     agent/pilot-runtime-replacement
expected_sha:   3f6e4196af4b9144ceaaba08f2b6637acdc1698d
required_parent: bf18638caeb1a01cd2e14e625d72a20893a04bb3
```

The authoritative acceptance manifest remains the source of truth for the canonical source repository, allowed changed paths, required files, case inputs, required statuses, mount/network constraints, and candidate authority rules.

## 3. Required runs

Exactly two authoritative `workflow_dispatch` runs are required.

### 3.1 Capability proof — `verify-candidate`

Question:

> Can the accepted candidate execute the authorized operation and produce independently verifiable evidence?

Required inputs:

```text
execution_mode: verify-candidate
target_ref: agent/pilot-runtime-replacement
expected_sha: 3f6e4196af4b9144ceaaba08f2b6637acdc1698d
```

This run is evidence of capability only. It is not evidence that the hostile boundary remains intact.

### 3.2 Boundary proof — `malicious-boundary-probe`

Question:

> Can candidate-controlled behavior influence the authoritative verdict or recreate any known false-success class?

Required inputs:

```text
execution_mode: malicious-boundary-probe
target_ref: agent/pilot-runtime-replacement
expected_sha: 3f6e4196af4b9144ceaaba08f2b6637acdc1698d
```

The probe succeeds only when malicious influence is rejected by the trusted boundary and cannot produce an authoritative terminal PASS. The GitHub workflow conclusion alone is not the verdict.

## 4. Evidence package

Evidence must be collected before interpretation. Each run receives an immutable directory identified by its GitHub run ID and attempt number.

```text
P1_EVIDENCE_PACKAGE/
├── protocol/
│   ├── P1_EVIDENCE_PROTOCOL.md
│   ├── protocol_commit_sha.txt
│   └── trusted_blob_identities.json
├── capability-proof_<run-id>_<attempt>/
│   ├── run_metadata.json
│   ├── workflow_run.txt
│   ├── commit_sha.txt
│   ├── environment.json
│   ├── input_contract.json
│   ├── acceptance_manifest.json
│   ├── raw_logs/
│   ├── artifacts/
│   ├── verifier_report.json
│   └── files_sha256.json
├── boundary-proof_<run-id>_<attempt>/
│   ├── run_metadata.json
│   ├── workflow_run.txt
│   ├── commit_sha.txt
│   ├── environment.json
│   ├── input_contract.json
│   ├── acceptance_manifest.json
│   ├── raw_logs/
│   ├── artifacts/
│   ├── verifier_report.json
│   └── files_sha256.json
├── replay/
│   ├── replay_environment.json
│   ├── replay_log.txt
│   ├── replay_report.json
│   └── files_sha256.json
└── final/
    ├── observation_report.md
    ├── verification_report.md
    ├── human_readability_review.md
    └── product_decision.md
```

### 4.1 Required run metadata

`run_metadata.json` must record at least:

- repository;
- workflow name and workflow file;
- workflow run ID, run attempt, event and timestamps;
- actual `github.workflow_sha` and `github.workflow_ref`;
- target ref, expected candidate SHA and observed candidate SHA;
- required parent SHA and observed parent SHA;
- execution mode;
- runner image/OS and relevant tool/container image identities;
- actor and the recorded human authorization reference;
- artifact names, sizes and SHA-256 hashes;
- final GitHub run conclusion, preserved as an observation only.

### 4.2 Raw evidence rule

Raw logs and downloaded artifacts must be preserved unchanged before a verifier report, replay result, summary, rerun, or remediation is written. The evidence package must contain a hash manifest covering every retained file.

Missing, expired, partial, altered, or unhashable evidence is not PASS.

## 5. Three-layer reporting

The final report must not mix the following layers.

### 5.1 Observation

Facts only:

- workflow run and attempt numbers;
- exact SHAs and refs;
- inputs;
- timestamps and environment;
- job and step outcomes;
- raw logs;
- artifacts and their hashes;
- actual files and values observed.

No product interpretation belongs in the observation report.

### 5.2 Verification

The trusted verifier and independent replay assess only:

```text
contract: PASS / FAIL
scope:    PASS / FAIL
evidence: PASS / FAIL
replay:   PASS / FAIL
```

The report must separately state:

```text
CAPABILITY PROOF: PASS / FAIL
BOUNDARY PROOF:   PASS / FAIL
```

Candidate tests, candidate reports, candidate-declared PASS, and a green workflow are observations only and have no independent authority.

### 5.3 Product decision

Only after the evidence package is sealed and replayed may the product owner issue exactly one verdict:

```text
P1 ACCEPT
P1 REWORK
P1 STOP
```

## 6. Success criteria

P1 may be accepted only when all of the following are true:

1. Both required dispatches ran with the exact frozen inputs.
2. The actual trusted proof-material blobs match the four frozen blob identities.
3. The actual candidate SHA and parent SHA match the frozen contract.
4. `verify-candidate` establishes the authorized capability with:
   - `contract: PASS`;
   - `scope: PASS`;
   - `evidence: PASS`.
5. `malicious-boundary-probe` establishes that hostile influence is rejected and cannot create authoritative PASS.
6. All required controller and execution evidence is present, hash-bound, internally consistent and attributable to trusted collectors/verifiers.
7. Candidate-controlled tests, reports and result declarations remain non-authoritative.
8. Independent replay from the sealed package, without candidate process memory, produces `replay: PASS` and the same authoritative conclusions.
9. Known false-success paths found during P1 work remain closed, and newly observed false-success paths equal zero.
10. No unresolved failure classification remains open.

A green GitHub workflow is neither necessary nor sufficient by itself. The authoritative contents of the evidence package decide the result.

## 7. Forbidden interpretations

The following statements are invalid:

```text
workflow green              == P1 ACCEPT
bootstrap merged            == P1 ACCEPT
candidate tests passed      == authoritative PASS
candidate declared PASS     == authoritative PASS
missing evidence            == PASS
NOT RUN                     == PASS
UNKNOWN                     == PASS
successful rerun            erases an earlier failed attempt
```

Every run attempt remains part of the record. A later run may provide new evidence but may not delete or rewrite the first failure.

## 8. First-failure rule

After the first failure, do not immediately change code, workflow, manifest, tests, protocol, or documentation and rerun.

First freeze the failed attempt and prepare:

```text
FAIL REPORT
Problem:
Evidence:
Expected:
Observed:
Impact:
Classification:
Affected proof layer:
Candidate influence possible: YES / NO / UNKNOWN
```

Only after the failure report is complete may a separate human decision authorize remediation or a new run.

## 9. Failure classification

One failure may receive more than one classification.

- `E-F001 — Implementation failure`  
  The candidate does not perform the authorized operation as contracted.

- `E-F002 — Evidence failure`  
  The operation may have occurred, but the system cannot prove it with complete, integrity-bound evidence.

- `E-F003 — Boundary failure`  
  Candidate-controlled state or behavior can influence the authoritative verdict or create a false-success path.

- `E-F004 — Environment failure`  
  The execution environment prevents the authorized proof from running or makes the observation incomplete.

- `E-F005 — Contract failure`  
  The frozen contract or success criteria are ambiguous, contradictory, or insufficient to decide the result.

Classification is not remediation. It records what failed before deciding what to do next.

## 10. Independent replay

Replay must be performed only after both raw evidence packages are sealed.

Replay must:

- start from a clean environment independent of the candidate process;
- use the frozen trusted verifier/manifest identities;
- verify all evidence-package hashes before interpretation;
- reconstruct candidate identity, controller identity, scope, result bundles, operation ledgers, environment observations and final gate inputs;
- reject missing or inconsistent data rather than infer it;
- produce a standalone `replay_report.json` containing `PASS` or `FAIL` and explicit reasons;
- require no undocumented process memory from the original workflow run.

## 11. Human readability review

This review is non-blocking for P1 but mandatory as a quality observation.

A person who does not know the implementation should be able to answer from the package:

1. What operation was authorized and executed?
2. On which exact code and source state?
3. Who authorized the proof run?
4. What did the trusted verifier conclude?
5. Why is the conclusion independent of the candidate?
6. Can the conclusion be reproduced from the retained evidence?

If answering requires reading implementation code, record `HUMAN_READABILITY: WEAK`; do not silently translate it into a technical PASS.

## 12. Product decision rules

### `P1 ACCEPT`

Permitted only when capability proof, boundary proof, contract, scope, evidence and replay all PASS; false-success paths are zero; and no unresolved failure classification remains.

### `P1 REWORK`

Use when the result is trustworthy enough to identify a remediable implementation, evidence, environment or contract defect, without weakening the trust boundary.

### `P1 STOP`

Use when completing P1 would require weakening the trust boundary, accepting candidate authority, treating missing evidence as PASS, or otherwise making the final claim less trustworthy than the protocol requires.

## 13. Change freeze and excluded work

From protocol freeze until the product verdict:

```text
NO EXECUTOR CODE CHANGES
NO WORKFLOW OR VERIFIER CHANGES
NO ACCEPTANCE-MANIFEST CHANGES
NO TEST CHANGES
NO PROTOCOL CHANGES UNDER THE RESULT
NO PR #29 WORK
NO GINSENG WORK
NO COS EXPANSION
NO SCRIPTOPS OR CLIENT TESTS
```

A necessary correction requires an explicit stop, preserved evidence, a new protocol version, and a new human authorization. It cannot retroactively alter the meaning of completed runs.

## 14. Execution order

```text
1. Freeze and approve this protocol.
2. Run verify-candidate.
3. Preserve and hash raw capability evidence.
4. Run malicious-boundary-probe.
5. Preserve and hash raw boundary evidence.
6. Perform independent replay.
7. Write OBSERVATION without interpretation.
8. Write VERIFICATION without scope expansion.
9. Perform the non-blocking human readability review.
10. Issue P1 ACCEPT / REWORK / STOP.
11. Only after the P1 verdict decide the status of PR #29.
12. Prepare P1_RETROSPECTIVE.md as a separate post-verdict record.
```

## 15. Protocol freeze rule

This document must be reviewed before the first authoritative dispatch.

After the first dispatch begins, its criteria are immutable for those run attempts. Any later clarification must be issued as a new version and may not be used retroactively to convert an observed FAIL, UNKNOWN, NOT RUN, or missing evidence into PASS.
