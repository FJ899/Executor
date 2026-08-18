# Independent Phase C Handoff

## Status model

`CORRECTIVE PHASE B / REVOCATION CUTOFF RE-PROOF / P4 NOT CLAIMED`

This committed document does not encode transient post-commit workflow conclusions. Every exact-candidate proof run exists only after the candidate commit exists. Immutable GitHub records establish post-commit facts for the exact SHA; mutable PR prose is locator/status metadata only.

Source hierarchy:

1. live exact `JTJ07/Executor#61` head commit/tree — implementation and policy candidate;
2. committed governance/policy/handoff documents — evidence contract and interpretation rules;
3. immutable GitHub Actions runs/artifacts/provider authority receipts — post-commit facts for that SHA;
4. PR #61 body — locator layer only;
5. fresh independent Phase C — final technical verdict, never supplied by the implementing agent.

## Human-selected constants

- DONE: P4 Repeatable Executor 1.0.
- Trusted front door/provider: external GitHub intake.
- Allowed human actor/profile: `trust_profiles/github-p4-pilots.json`.
- Solution ownership: External Intelligence without effect authority.
- Pilot repositories: `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`.
- Supported class: `BOUNDED_CORRECTNESS_OR_QUALITY_FIX` within frozen profile limits.
- External effects: dedicated branch, commit and draft PR only.
- Forbidden without separate authorization: merge, deploy, release, tag, new secrets, new credentials and new paid services.

## Human-approved revocation cutoff

On 2026-08-17 the human accepted:

```text
AKCEPTUJĘ REVOCATION CUTOFF AT GLOBAL CONTRACT_ACCEPT CONSUMPTION
AKCEPTUJĘ FINAL LIVE VERIFICATION AS REVOCATION CUTOFF BOUND INTO SUCCESSFUL GLOBAL CONTRACT_ACCEPT CONSUMPTION
```

Phase C must interpret G-04 accordingly:

- **pre-cutoff:** current request/ACCEPT edit, deletion, mismatch, invalid origin or expiry must block final live verification / `CONTRACT_ACCEPT`;
- final live verification produces exact snapshot `S`;
- `S` is authority only if exact `S` is successfully globally consumed as `CONTRACT_ACCEPT` and the resulting frozen decision/result binding is valid;
- final verification success + failed global consumption = no authority; retry requires a new final live verification;
- **post-cutoff:** later source request/comment mutation does not retroactively revoke or alter the already consumed/frozen `S`;
- Stage B must use frozen `S` + successful `CONTRACT_ACCEPT` receipt, not mutable GitHub currentness, before independently applying normal EFFECT authority controls.

GitHub does not provide and Executor does not claim a cross-resource atomic Issue/Comment + Git-ref transaction. The accepted system linearization point is the final live verified snapshot conditional on successful global `CONTRACT_ACCEPT` consumption.

## Historical rejected or superseded candidates

Raw evidence remains historical evidence for the exact SHA that produced it. It does not satisfy a later exact-candidate gate.

- `24107bc8a8186ed1928e098118982efb9d62ffaa` — `FALSE-COMPLETION`: global replay/uniqueness boundary.
- `7f662cd487c14d62a4838be8c43cef1358869d50` — `BLOCKED`: G-02 canonical truth and G-14 exact-head CI binding.
- `fdf876e0e2af6d9e4ecea2301ecb686a471037bd` — `FALSE-COMPLETION`: app-mediated events not fail-closed as non-human.
- `d11f3dd9d6c484a9c554cd562db46c30e0a333fe` — `FALSE-COMPLETION`: effect freshness TOCTOU.
- `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` — its six-run P4 workflow DID execute and produced exact-SHA raw evidence. A later G-04 finding showed that revocation-cutoff semantics were not correctly represented: Stage B still re-read mutable GitHub request/comment state, permitting post-freeze provider mutation to behave as retroactive revocation. The old evidence remains historical; the prior verdict is superseded and cannot satisfy the new candidate.

All direct-human ACCEPT events consumed by these candidates, including ACCEPT 001–012, are historical/consumed authority and must not be reused.

`VERDICT superseded != EVIDENCE erased`.

## Corrective architecture to verify

Phase C must independently prove:

- `github-pilot-decide` uses the existing authoritative GitHub trust verifiers for the final live read immediately before `CONTRACT_ACCEPT`;
- the exact final provider request/decision evidence becomes an immutable snapshot containing provider identity, body hashes/payloads, immutable IDs, exact request/draft binding, direct-human provenance, edit/freshness state and pinned target commit/tree;
- the snapshot SHA-256 is the payload bound into local/global `CONTRACT_ACCEPT` receipts;
- no `AUTHORIZED_AND_FROZEN` result exists unless the successful FINAL receipt/result relationship matches that exact snapshot;
- a failed global consumption produces no frozen authority and no reusable cached snapshot;
- `run-pilot` validates immutable frozen authority + successful `CONTRACT_ACCEPT` receipt and does not re-fetch mutable request/comment state as retroactive revocation;
- `CONTRACT_ACCEPT` and EFFECT are separate one-shot consumptions;
- effect authorization still re-samples time after preconditions, binds frozen decision expiry into EFFECT `not_after`, and requires provider `provider_created_at < not_after` before local effect consumption/mutation;
- provider-backed Git refs remain global one-shot uniqueness; SQLite remains local crash-safe evidence/result binding;
- exact workflow/image/source/proposal identities remain bound;
- solution provenance remains post-request, exact-bound, zero-human-edit and effect-capability `NONE`;
- zero-test, source/scope/link/isolation/cleanup and false-success controls remain fail-closed.

## Mandatory revocation falsification matrix

- FC-09 PRE-CUTOFF ACCEPT EDIT — block before CONTRACT_ACCEPT/freeze.
- FC-10 PRE-CUTOFF ACCEPT DELETE — block before CONTRACT_ACCEPT/freeze.
- FC-11 PRE-CUTOFF REQUEST MUTATION — old decision cannot authorize changed request.
- FC-12 FINAL VERIFY + FAILED GLOBAL CONSUMPTION — no authority; retry re-verifies live provider state.
- FC-13 POST-CUTOFF ACCEPT EDIT — frozen authority remains valid; EFFECT controls still apply.
- FC-14 POST-CUTOFF ACCEPT DELETE — frozen authority remains valid.
- FC-15 POST-CUTOFF REQUEST EDIT — frozen request meaning remains the consumed snapshot.
- FC-16 SNAPSHOT SUBSTITUTION — altered identity/hash/snapshot not matching receipt blocks.
- FC-17 CONTRACT_ACCEPT REPLAY — different run/fresh SQLite/another consumer cannot create another freeze from the same one-shot authority.

FC-01–FC-08 and all prior G-04/G-06/security regressions remain mandatory.

## Consequential series boundary

The old `eca7eeb...` six-run series is historical only. The corrective candidate must not reuse its ACCEPTs or artifacts as current consequential proof.

The committed P4 workflow is manual `workflow_dispatch` only and takes six explicit fresh ACCEPT comment IDs. A PR-head synchronization must not launch it. This corrective Phase B stops before fresh human authority, so no new P4 series is run now.

After fresh human authority is later supplied, a new exact-head series must contain:

- two authorized objectives / two authorized repositories;
- three separately direct-human-authorized executions per objective;
- six new `CONTRACT_ACCEPT` snapshots/receipts and six separate EFFECT authority chains;
- same exact pinned source per objective and reproducible patch;
- frozen postconditions/regressions, scope/isolation and immutable workflow/image/source evidence;
- target PRs still OPEN/DRAFT/UNMERGED unless separately authorized otherwise.

## Non-consequential exact-candidate evidence required before asking for fresh authority

For the corrective head, verify:

- exact-head `Verify Executor foundations` CI, including full unit discovery, compile, wheel/install CLI smoke and validators;
- exact-head Docker sandbox security job and cleanup;
- exact-head GP001 replay repeatability;
- FC-09–FC-17 plus existing replay/freshness/provenance/zero-test/security regressions;
- documentation/current-state G-02 reconciliation;
- consequential P4 workflow did **not** run from the corrective push and contains no historical ACCEPT IDs.

## Completion boundary

Until a fresh consequential series and independent Phase C exist:

```text
P4: NOT CLAIMED
EXECUTOR 1.0: NOT HUMAN-ACCEPTED
OLD eca7eeb P4 EVIDENCE: HISTORICAL ONLY
FRESH ACCEPT SERIES: REQUIRED
MERGE / RELEASE / DEPLOY / TAG: NOT AUTHORIZED
G-18: NOT AVAILABLE
```

Only after a future fresh exact-head consequential series exists may an independent Phase C evaluate G-01–G-17. G-18 remains a separate explicit human decision and is never implied by CI, this file, PR metadata or an AI statement.
