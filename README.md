# Creative OS Executor

Repozytorium: `JTJ07/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Executor jest runtime wykonawczym większego systemu Creative OS. Otrzymuje zatwierdzony kierunek i zamienia go w odwracalne, testowalne działanie. Nie zastępuje Ginsenga ani warstw deliberacyjnych. Executor nie jest właścicielem celu.

## Current product / reproof state

Historyczny exact candidate `f60829f90ea2f69dc501582daf109b59676be07e` został w 2026-08-18 niezależnie zweryfikowany, zaakceptowany przez Human jako `EXECUTOR 1.0: ACCEPT` i później zintegrowany na `main`. Ta decyzja pozostaje ważnym historycznym faktem dla tamtej exact identity.

Późniejszy finish-line recheck z 2026-08-19 wykazał brakujące dowody dla kosztu, dependency-change stability i trusted Phase-C provenance. Tego snapshotu nie przepisujemy wstecz. Zamiast tego wykonano świeży changed-identity proof dla późniejszego exact candidate:

```text
CURRENT REPROOF TARGET: 3cd0c8d747fef06f82c01cdab8449c7c8a100038
TREE: c739aaa989a15eaed65996d7a0b5242a0ec26d7e
FRESH CONSEQUENTIAL RUN: 32404181188
TRUSTED READ-ONLY VERIFIER RUN: 32407901358
G-13: PASS
G-15: PASS
G-17: PASS
```

Fresh dependency cycle:

```text
PyYAML==6.0.2 -> PyYAML==6.0.3
6 executions = 3 ScriptOps + 3 Reconstructor
reviewed output coverage = 6/6
task semantics change = false
capability change = false
```

The exact run94 verifier extension was separately accepted by the Human as a trust root for read-only G-17 use. The verifier itself cannot create G-18.

This branch is only a **claim/repository-closure reconciliation candidate**. Until its exact reconciliation state is separately authorized and merged, canonical `main` has not adopted the current precedence correction.

```text
G-02: CANDIDATE / AWAITS CANONICAL INTEGRATION
G-16: CANDIDATE / AWAITS CANONICAL INTEGRATION
G-18 FOR 3cd0c8d...: NOT SUPPLIED
PROJECT COMPLETION FOR CURRENT REPROOF TARGET: NOT YET CLAIMED
```

The historical G-18 for `f60829f...` is preserved and is not silently transferred to `3cd0c8d...`.

Still **not authorized**:

```text
MERGE OF THIS RECONCILIATION CANDIDATE
MERGE OF TARGET PILOT OUTPUTS
RELEASE
DEPLOYMENT
TAG
NEW SECRETS / CREDENTIALS
NEW PAID SERVICES
BROADER EXTERNAL EFFECTS
NEW PRODUCT CAPABILITY
```

## Exact fresh evidence locators

Consequential run:

```text
GitHub Actions run: 32404181188
ScriptOps artifact: 9419652927
ScriptOps artifact sha256: b26cae6737cdd01d1d63fdaa0addba493d77f6a385ce225f8f4a26c87fc89b87
ScriptOps repeated patch sha256: c9c355db350382ab98b3edaf4d0794c50905816b45ec077f8fdc675b0b856007

Reconstructor artifact: 9419647722
Reconstructor artifact sha256: b76d52f569531e537cacc950a30e0ffd9206f09f24dda9926ce20e83aa358f7d
Reconstructor repeated patch sha256: 56081b656827ad7247b1a95647fff8f9a2b3476ccd719308bd9e39a650299d2c
```

Trusted read-only reproof:

```text
Verifier branch head: e73f1d410e663c85f7552ac92a492ef45d6a2901
Verifier extension sha256: 74d4b9f7e4acaa5bfb670cfe089bc087bf95a285b56552f88507cda4e5785cf6
Verifier manifest sha256: 050358461cbebe1cb11a1611635243a255440aad582310493cf5034eaec15568
Verifier run: 32407901358
Verifier artifact: 9420977465
Verifier artifact sha256: dbe3f35f7d9761959634ebbc6182a0987d74e9a8d359bb91ba95f804c19cfd21
```

## Implemented scope

Executor preserves exact identity, verified Human authority, immutable freeze, separated solution provenance, atomic effect authority, isolated execution, evidence and review-required terminal semantics for the bounded supported P4 task class.

Generic arbitrary external-project execution and auto-merge remain outside the accepted bounded scope. Technical success never authorizes merge, release or deployment.

## Start

```bash
python -m unittest discover -s tests -v
python -m compileall -q executor
python -m executor.cli --help
python -m executor.cli validate-project project_contracts/executor-self.yaml --policy EXECUTOR_POLICY.yaml --base-dir .
python -m executor.cli validate-test test_contracts/examples/valid_test.yaml --base-dir tests/fixtures --holdout-evidence tests/fixtures/holdout_evidence.json
```

Pliki `.yaml` używają składni JSON, poprawnego podzbioru YAML 1.2.

## Jak czytać repo — źródła prawdy

`README.md` jest indeksem i skrótem. Nie nadpisuje dedykowanych kontraktów ani evidence records.

- `docs/governance/DOCUMENT_AUTHORITY.md` — ownership źródeł prawdy i precedence;
- `evidence/phase-c/P4_RUN94_FINAL_CLAIM_RECONCILIATION_2026-08-20.md` — current run94 reproof/claim-state reconciliation candidate;
- `evidence/phase-c/P4_FINISH_LINE_GATE_RECHECK_2026-08-19.md` — historical finish-line gap snapshot, intentionally not rewritten;
- `docs/governance/EXECUTOR_1_0_FINAL_COMPLETION_RECORD_2026-08-18.md` — historical final Human acceptance/integration record for `f60829f...`;
- `PROJECT_COMPLETION_MAP.md` — Human-approved G-01–G-18 DONE contract; older result text is historical for the earlier exact accepted chain;
- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` — P-level definitions and P4 evidence semantics;
- `docs/product/P4_REPEATABILITY_POLICY.md` — P4 repeatability/change-regression and execution-identity policy;
- `ACTION_AUTHORIZATION_PACKET_v1.0.md` — exact action-authorization semantics;
- `EXECUTOR_POLICY.yaml` — deterministic execution policy.

Open/branch-only reconciliation content is non-canonical until merged. Historical consumed authority evidence remains exact-SHA evidence and must not be reused as fresh authority.

## Accepted authority model

The bounded P4 path preserves two distinct authority stages:

```text
MUTABLE REQUEST / ACCEPT
  -> FINAL LIVE PROVIDER VERIFY
  -> IMMUTABLE AUTHORITY SNAPSHOT
  -> GLOBAL CONTRACT_ACCEPT
  -> AUTHORIZED_AND_FROZEN

AUTHORIZED_AND_FROZEN
  -> PROPOSAL / POLICY / PRECONDITIONS
  -> EFFECT AAP + GLOBAL EFFECT RESERVATION
  -> PROVIDER-TIME FRESHNESS
  -> LOCAL CONSUME
  -> MUTATION / EVIDENCE / RESULT BINDING
```

A valid AAP means only `READY_FOR_ATOMIC_CONSUMPTION`; it is never proof that an effect happened.

## Truthful completion semantics

```text
TECHNICAL PASS != FINAL HUMAN ACCEPTANCE
INDEPENDENT VERIFIER PASS != G-18
HISTORICAL G-18 FOR ONE EXACT SHA != G-18 FOR A LATER EXACT SHA
PRODUCT ACCEPTANCE != MERGE
MERGE != RELEASE / DEPLOY / TAG
```

For the current reproof target, the next admissible transition after a separately authorized exact reconciliation merge is a fresh read-only exact-main G-02/G-16 audit. Only after G-01–G-17 are established at one reconciled state may the Human supply or withhold the exclusive final G-18 decision.
