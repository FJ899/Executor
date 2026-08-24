# Creative OS Executor

Repozytorium: `FJ899/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Executor jest runtime wykonawczym większego systemu Creative OS. Otrzymuje zatwierdzony kierunek i zamienia go w odwracalne, testowalne działanie. Nie zastępuje Ginsenga ani warstw deliberacyjnych. Executor nie jest właścicielem celu.

## Current product state

Executor 1.0 is no longer a Phase-B candidate. The selected P4 product claim passed the fresh Run94 consequential reproof, was independently re-derived through the separately Human-accepted read-only verifier trust root, was canonically reconciled on `main`, and then received a new direct Human G-18 acceptance for the exact Run94 implementation identity.

```text
EXECUTOR 1.0 PRODUCT: HUMAN ACCEPTED
SELECTED ENDPOINT: P4 REPEATABLE EXECUTOR 1.0
PROJECT COMPLETION: PASS
G-01–G-18: PASS
IMPLEMENTATION INTEGRATION: COMPLETE
FINAL HUMAN-ACCEPTED CANDIDATE: 3cd0c8d747fef06f82c01cdab8449c7c8a100038
FINAL HUMAN-ACCEPTED TREE: c739aaa989a15eaed65996d7a0b5242a0ec26d7e
FRESH CONSEQUENTIAL RUN: 32404181188
TRUSTED INDEPENDENT VERIFIER RUN: 32407901358
CANONICAL MAIN AT FINAL ACCEPTANCE: a7fc272e09a2ffb5c06a98e26ed6ef9667cd4f89
ACTIVE PRODUCT COMPLETION GATE: NONE
```

Current Run94 acceptance is persisted in:

- `docs/governance/EXECUTOR_1_0_FINAL_HUMAN_ACCEPTANCE_RECORD_2026-08-20.md`.

The earlier 2026-08-18 acceptance/integration chain remains preserved as historical provenance in:

- `docs/governance/EXECUTOR_1_0_FINAL_COMPLETION_RECORD_2026-08-18.md`;
- `evidence/phase-c/EXECUTOR_1_0_POST_INTEGRATION_CLOSURE_2026-08-18.md`.

Still **not authorized** by product acceptance or integration:

```text
MERGE OF TARGET PILOT PRs
FURTHER MERGE
RELEASE
DEPLOYMENT
TAG
NEW SECRETS / CREDENTIALS
PAID SERVICES
BROADER EXTERNAL EFFECTS
NEW PRODUCT-DEVELOPMENT PHASE
```

Any such future effect is a new phase and requires its own Human authority and appropriate evidence.

## Implemented scope

The accepted implementation contains the earlier foundations and the later bounded P4 path. Historical labels such as M0/M1/M2A/M2B remain useful architecture/provenance names; they are no longer a current completion queue.

Sandbox execution uses Docker without host fallback. The governed path preserves exact identity, policy, authority consumption, isolation, evidence and review-required terminal semantics. Generic arbitrary external-project execution and auto-merge remain outside the accepted bounded scope.

### Historical P0 evidence binding — preserved provenance

P0 was an earlier accepted product checkpoint. Its exact binding remains durable historical evidence and is intentionally preserved even though the current product state has advanced to Human-accepted P4:

```text
P0 ACHIEVED SHA: b092a85e82eb81ec6dc7db4a7064409c6c383359
P0 EVIDENCE PR: #16
P0 EVIDENCE RUN ID: 30755381646
P0 HUMAN DECISION: ACCEPTED THROUGH MERGE OF PR #16
```

These fields are provenance for P0 only. They do not compete with, downgrade or replace the later P4 completion/acceptance chain.

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

`README.md` jest indeksem i skrótem statusu. Nie nadpisuje dedykowanych kontraktów ani finalnych evidence records.

Minimalny current zero-history recovery z tego entrypointu musi objąć: `README.md` → `docs/governance/DOCUMENT_AUTHORITY.md` → `docs/governance/EXECUTOR_1_0_FINAL_HUMAN_ACCEPTANCE_RECORD_2026-08-20.md` → `docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md`. Nie kończ recovery przed odczytaniem pointera do Human-owned `AKCJA / GDZIE / ODESŁAĆ`.

- `docs/governance/DOCUMENT_AUTHORITY.md` — ownership źródeł prawdy i precedence;
- `docs/governance/EXECUTOR_1_0_FINAL_HUMAN_ACCEPTANCE_RECORD_2026-08-20.md` — current Run94 Human G-18 acceptance, exact accepted identity and current completion pointer;
- `docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md` — required current zero-history pointer to the Human-owned `AKCJA / GDZIE / ODESŁAĆ` interaction contract;
- `docs/governance/EXECUTOR_1_0_FINAL_COMPLETION_RECORD_2026-08-18.md` — historical 2026-08-18 Human-accepted completion state and exact accepted identity;
- `evidence/phase-c/EXECUTOR_1_0_POST_INTEGRATION_CLOSURE_2026-08-18.md` — historical verified integration and post-integration closure facts;
- `evidence/phase-c/P4_RUN94_FINAL_CLOSURE_RECONCILIATION_2026-08-20.md` — pre-G-18 Run94 G-01–G-17/G-02/G-16 canonical closure state;
- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md` — cel produktu i granice ekosystemu;
- `PHASE_B_AUTHORIZATION.md` — historical Human-selected DONE/trust/effect semantics used to reach the accepted candidate;
- `PROJECT_COMPLETION_MAP.md` — Human-approved G-01–G-18 completion contract and historical Phase-B execution map; current gate result is final PASS, not Phase-B ACTIVE;
- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` — definicje poziomów maturity/proof, nie kolejka implementacyjna;
- `docs/product/P4_REPEATABILITY_POLICY.md` — P4 retry/repeatability oraz rozdział CONTRACT_ACCEPT vs EFFECT;
- `ACTION_AUTHORIZATION_PACKET_v1.0.md` — terminalny kontrakt autoryzacji consequential action;
- `EXECUTOR_POLICY.yaml` — deterministyczna polityka wykonania.

Otwarty draft PR, branch-only dokument albo komentarz review nie zmienia kanonu `main` przed merge. Historical candidate and consumed authority evidence remain exact-SHA evidence only and must not be reused as new authority.

## Accepted authority model

The accepted P4 path preserves two different authority stages:

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

Before the accepted CONTRACT_ACCEPT cutoff, edit/delete/mismatch/expiry blocks. Successful freeze does not collapse CONTRACT_ACCEPT and EFFECT into one authority. A valid AAP means only `READY_FOR_ATOMIC_CONSUMPTION`; it is never proof that an effect happened.

## Historical candidate evidence

Earlier P4 evidence at `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` remains historical-only because a later G-04 finding superseded its completion verdict. The corrective path then produced the separately Human-accepted 2026-08-18 candidate `f60829f...`. That identity remains historical provenance after the later Run94 dependency-change reproof and new direct Human acceptance for `3cd0c8d...`.

```text
OLD eca7eeb P4 EVIDENCE: HISTORICAL ONLY
ACCEPT 001–012 FROM THAT SERIES: HISTORICAL / CONSUMED / MUST NOT BE REUSED
2026-08-18 HUMAN-ACCEPTED P4 CANDIDATE: f60829f90ea2f69dc501582daf109b59676be07e
CURRENT RUN94 HUMAN-ACCEPTED P4 CANDIDATE: 3cd0c8d747fef06f82c01cdab8449c7c8a100038
P4 REPEATABLE EXECUTOR 1.0: HUMAN ACCEPTED
PROJECT COMPLETION: PASS
```

`VERDICT superseded != EVIDENCE erased`.

## Truthful completion semantics

A technical `PASS` never automatically means `HUMAN ACCEPTED`, `PRODUCT ACCEPTED`, `MERGED`, release or deployment. In this project the current product claim is valid because the fresh Run94 evidence chain, the separately accepted trusted verifier, the canonical closure state and the explicit Human G-18 decision exist and are bound in the current final acceptance record.

```text
TECHNICAL / PHASE-C EVIDENCE: PASS
PROJECT COMPLETION: PASS
EXECUTOR 1.0: ACCEPT
P4 REPEATABLE EXECUTOR 1.0: HUMAN ACCEPTED
IMPLEMENTATION INTEGRATION: COMPLETE
FALSE SUCCESS PATHS FOUND IN CURRENT ACCEPTED EVIDENCE CHAIN: 0
```
