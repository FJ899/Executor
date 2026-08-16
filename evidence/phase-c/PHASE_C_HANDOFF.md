# Independent Phase C Handoff

## Status

`PHASE C FALSE-COMPLETION RECORDED / CORRECTIVE SERIES AUTHORIZED / EXECUTION PENDING / NEW PHASE C NOT READY`

Independent Phase C rejected historical Executor candidate `24107bc8a8186ed1928e098118982efb9d62ffaa`. The executing agent is correcting the implementation under the unchanged human-approved completion map. No current SHA is a completion candidate until this document is explicitly advanced to `READY FOR FRESH PHASE C` after the corrected series and exact-head evidence pass.

The verifier must always resolve the exact current head/tree of `JTJ07/Executor#61`; historical successful workflows or artifacts never substitute for evidence tied to a later corrected candidate.

## Human-selected constants

- DONE: P4 Repeatable Executor 1.0.
- Trusted front door/provider: external GitHub intake.
- Allowed actor/profile: `trust_profiles/github-p4-pilots.json`.
- Solution ownership: External Intelligence without effect authority.
- Pilot repositories: `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`.
- Effects: dedicated branch, commit and draft PR only.
- Forbidden: merge, deploy, release, new secrets, new credentials and new paid services unless separately authorized.

## Rejected Phase-C findings that are now mandatory regression targets

The corrected candidate must independently falsify each prior failure:

1. **Same-ledger replay:** changing caller-controlled `run_id` must not mint a new effect authority key from one human decision.
2. **Cross-ledger replay:** choosing a different local SQLite file or runner must not create a fresh authority namespace.
3. **Solution provenance:** proposal evidence must prove a post-request External Intelligence derivation with provider/model/prompt hash, zero human solution edits and no effect capability.
4. **Environment identity:** exact workflow file identity and resolved Docker image identity must be integrity-bound into action/result evidence, not recoverable only from logs.
5. **Silent zero-test regression:** a declared unittest discovery that runs zero tests must produce `BLOCKED`, never aggregate regression PASS.
6. **P4 series evidence:** the completion candidate must meet the repeatability series/metrics policy rather than infer P4 from two successful patch reviews.
7. **Canonical truth:** README/inventory/manifest/handoff/value evidence must all distinguish historical rejected evidence from the current candidate.

## Corrective architecture under test

The open branch currently introduces:

- deterministic GitHub provider-backed authority receipt refs shared across runners/local databases;
- local SQLite retained as crash-safe consumption/result evidence, not the global uniqueness root;
- one stable effect authority identity per human decision + frozen contract, independent of `run_id` and proposal variation;
- exact workflow/image environment identity included in terminal evidence and integrity-bound into the effect packet;
- post-request proposal provenance validation;
- fail-closed zero-test discovery handling;
- explicit P4 retry/model/dependency/series policy in `docs/product/P4_REPEATABILITY_POLICY.md`.

These are implementation candidates only. Their presence is not proof until exact-head tests and real corrected pilot evidence pass.

## Historical real outputs retained, not accepted as corrected P4 evidence

- ScriptOps request #62 / PR `JTJ07/scriptops#8` / human review APPROVED.
- Reconstructor request #63 / PR `JTJ07/creative-os-project-reconstructor#4` / human review APPROVED.

The historical Reconstructor request contains a regression discovery command that executed zero tests, so that request cannot be silently reused as corrected regression evidence. A new direct-human request was therefore created as issue #64 with a meaningful non-empty regression set. ScriptOps was likewise re-issued as #65 for the corrected series.

Historical human-time observations remain in `P4_VALUE_METRICS.md`, with their interpretation bounded to patch review effort only.

## Corrected direct-human authority set

ScriptOps issue #65, draft SHA `cfdcfa2ac6b2d6ac7e3da59b0d7aece0e54d43e99f3c8977e8cd422285b50cf6`:

- comment `5309032642` — `p4-scriptops-corrected-accept-001`;
- comment `5309033360` — `p4-scriptops-corrected-accept-002`;
- comment `5309034120` — `p4-scriptops-corrected-accept-003`.

Reconstructor issue #64, draft SHA `49f3ae5290220ed70db4d257f4abfec1ed67af67da9c9b9c4a1ff026a6a2863e`:

- comment `5309040666` — `p4-reconstructor-corrected-accept-001`;
- comment `5309041408` — `p4-reconstructor-corrected-accept-002`;
- comment `5309042154` — `p4-reconstructor-corrected-accept-003`.

All six events were observed as direct `JTJ07` / user-id `219382941` owner comments with exact request/draft binding and distinct nonces. They authorize six separate bounded attempts only; they do not authorize merge, release or deployment.

## Evidence requirements for the next handoff

Before this handoff may become `READY FOR FRESH PHASE C`, the branch must contain and/or point to:

- green exact-head foundation CI and GP001 replay;
- explicit tests for same-decision different-`run_id` replay;
- explicit tests for same-decision different-local-ledger replay;
- provider-backed global reservation/final result receipts from real GitHub Actions;
- the six fresh direct-human decision events above, each consumed at most once;
- the approved P4 series for this candidate: two distinct real bounded objectives across the two authorized repositories, each repeated three times under separate fresh ACCEPT events;
- durable post-request solution provenance for each proposal;
- exact source commit/tree, exact workflow SHA and resolved image ID in each artifact;
- meaningful non-empty regression evidence where a test-discovery command is declared;
- draft-only target outputs and human reviews;
- corrected P4 series metrics, failure taxonomy, latency, cost disclosure and model/dependency stability evidence;
- repository closure state and no contradictory active success claim.

Each pilot artifact must permit independent recomputation from raw material and include its local SQLite ledger plus locators for the provider-backed authority receipts.

## Next independent verification

A fresh verifier must reconstruct G-01 through G-18 from `PROJECT_COMPLETION_MAP.md` and specifically attempt to recreate the prior false-success paths. It must not rely on this executing agent's statement that the fixes work.

Until this file is advanced after the corrected series, the only truthful completion state is:

```text
PROJECT COMPLETION: NOT READY FOR RE-VERIFICATION
P4: NOT CLAIMED
MERGE / RELEASE / DEPLOY: NOT AUTHORIZED
```
