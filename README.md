# Creative OS Executor

Repozytorium: `JTJ07/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Executor jest runtime wykonawczym większego systemu Creative OS. Otrzymuje zatwierdzony kierunek i zamienia go w odwracalne, testowalne działanie. Nie zastępuje Ginsenga ani warstw deliberacyjnych. Executor nie jest właścicielem celu.

Aktualny pierwszy produktowy pion to wykonanie dobrze określonego zadania technicznego w repozytorium i pokazanie zmiany wraz z weryfikacją. Zabezpieczenia, sandbox i dowód są fundamentami uczciwego wykonania, ale nie stanowią głównego celu produktu.

Zakres na kanonicznym `main` obejmuje:

- **M0 — Test Contract Validator**;
- **M1 — Project Contract + Policy Engine**;
- **M2A — State Machine + Checkpointy**;
- **M2B — Izolowany Sandbox dla fixtures**.

Sandbox używa backendu Docker bez fallbacku do wykonania na hoście. Profil wymusza read-only root/source, osobny tmpfs workspace, brak sieci i sekretów, niedostępny HOME, non-root, usunięte capabilities, limity zasobów/czasu oraz cleanup. Polityka, source, obraz i własność kontenera są wiązane z niezmiennymi identyfikatorami oraz weryfikowane fail-closed.

Kandydat Phase B rozwija ten rdzeń bez włączania generycznego external execution. Polityka utrzymuje `external_projects: false` i dopuszcza wyłącznie dwa nazwane repozytoria pilotażowe oraz draft PR bez merge. Dopóki implementacyjny PR nie zostanie zaakceptowany i scalony, jest to praca review-branch, a nie kanon `main`.

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

`README.md` jest indeksem i skrótem statusu. Nie nadpisuje dedykowanych kontraktów.

- `docs/governance/DOCUMENT_AUTHORITY.md` — ownership źródeł prawdy i precedence;
- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md` — cel produktu i granice ekosystemu;
- `PHASE_B_AUTHORIZATION.md` — human-selected DONE/trust/effect boundaries oraz jawne semantyczne decyzje człowieka;
- `PROJECT_COMPLETION_MAP.md` — G-01–G-18 i definicja ukończenia;
- `docs/product/P4_REPEATABILITY_POLICY.md` — P4 retry/repeatability oraz rozdział CONTRACT_ACCEPT vs EFFECT;
- `docs/architecture/IMPLEMENTATION_INVENTORY.md` — datowany obraz kandydata;
- `docs/product/P4_GITHUB_PILOT_OPERATOR_GUIDE.md` — operator path;
- `evidence/phase-c/PHASE_C_HANDOFF.md` — kontrakt niezależnej weryfikacji;
- `ACTION_AUTHORIZATION_PACKET_v1.0.md` — terminalny kontrakt autoryzacji consequential action;
- `EXECUTOR_POLICY.yaml` — deterministyczna polityka wykonania.

Otwarty draft PR, branch-only dokument albo komentarz review nie zmienia kanonu `main` przed merge. Dla aktywnego kandydata dokładny PR head/tree określa implementację, a immutable exact-head runs/artifacts/provider receipts określają post-commit facts.

## Human-approved revocation cutoff

Phase B posiada jawną decyzję człowieka:

```text
AKCEPTUJĘ FINAL LIVE VERIFICATION AS REVOCATION CUTOFF BOUND INTO SUCCESSFUL GLOBAL CONTRACT_ACCEPT CONSUMPTION
```

Kandydat implementuje dwa różne etapy authority:

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

Przed cutoffem edit/delete/mismatch/expiry blokuje. Snapshot staje się authority wyłącznie po udanym globalnym `CONTRACT_ACCEPT`; failed consumption tworzy zero authority i retry musi wykonać nową live verification. Po udanym cutoffie późniejsza mutacja źródłowego GitHub Issue/Comment nie revokuje retroaktywnie zamrożonego kontraktu. `run-pilot` korzysta z immutable frozen snapshot + successful CONTRACT_ACCEPT receipt i nie przywraca mutable GitHub currentness jako drugiego modelu revocation.

To nie osłabia effect-side controls. CONTRACT_ACCEPT i EFFECT są odrębnymi one-shot consumptions.

## Action Authorization Packet

Poprawny AAP oznacza wyłącznie:

```text
READY_FOR_ATOMIC_CONSUMPTION
```

Nie jest dowodem wykonania. Kandydat Phase B dodaje global one-shot authority, trwały lokalny ledger oraz dokładne związanie wyniku. Claim pozostaje kandydatem do czasu pełnego exact-head evidence, niezależnej Phase C i finalnej decyzji człowieka.

## Build status versus maturity

```text
CURRENT HUMAN-SELECTED TARGET: P4 — REPEATABLE EXECUTOR 1.0
TRUST DOMAIN: GITHUB / EXTERNAL GOVERNED INTAKE
SOLUTION OWNER: EXTERNAL INTELLIGENCE
PILOT CLASS: JTJ07/scriptops + JTJ07/creative-os-project-reconstructor / DRAFT PR ONLY

CURRENT PROVEN PRODUCT LEVEL: P0 — FOUNDATION / ACHIEVED IN DECLARED SCOPE
ACTIVE MATURITY CLAIM: NONE
P4 REQUIRES: ALL APPLICABLE GATES + FRESH CONSEQUENTIAL EVIDENCE + INDEPENDENT PHASE C + FINAL HUMAN ACCEPTANCE
```

Techniczny `PASS` nie oznacza automatycznie `PRODUCT ACCEPTED`, `HUMAN ACCEPTED`, `MERGED` ani maturity advancement.

## Current candidate / historical P4 evidence

The six-run P4 series at exact Executor head `eca7eebbb4bead819cfd35ecd81b3200cc6e461a` **did run** and its immutable raw evidence remains historical evidence for that exact SHA. A later G-04 finding superseded its prior completion verdict because the contract-freeze revocation cutoff was not yet represented correctly and Stage B re-read mutable provider state.

Therefore:

```text
OLD eca7eeb P4 EVIDENCE: HISTORICAL ONLY
ACCEPT 001–012: HISTORICAL / CONSUMED / MUST NOT BE REUSED
NEW EXACT CANDIDATE: REQUIRES FRESH CONSEQUENTIAL AUTHORITY LATER
P4 REAL-PILOT WORKFLOW: MANUAL workflow_dispatch ONLY
CORRECTIVE PUSH: MUST NOT RUN THE SIX-EXECUTION SERIES
P4: NOT CLAIMED
PHASE C: NOT YET RUN FOR THE NEW CANDIDATE
FINAL HUMAN ACCEPTANCE: NOT AVAILABLE
```

`VERDICT superseded != EVIDENCE erased`.

## Status implementacji

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B: IMPLEMENTED / FIXTURES VERIFIED
M3+: NOT CLAIMED ON MAIN
GP001 PRODUCT PATH: REAL FIXTURE E2E + REPLAY ACCEPTED IN DECLARED SCOPE
REQUEST TO CONTRACT: PHASE 1 IMPLEMENTED / CLI SURFACE IN PHASE B CANDIDATE
GITHUB REQUEST + DECISION TRUST: IMPLEMENTED CANDIDATE
CONTRACT_ACCEPT REVOCATION CUTOFF: IMPLEMENTED CANDIDATE / FINAL-LIVE SNAPSHOT + GLOBAL ONE-SHOT BINDING
POST-CUTOFF AUTHORITY SOURCE: FROZEN SNAPSHOT + SUCCESSFUL CONTRACT_ACCEPT RECEIPT
ACTION AUTHORIZATION PACKET: VALIDATOR + ATOMIC LEDGER + RESULT BINDING IMPLEMENTED CANDIDATE
EXTERNAL SOLUTION INTERFACE: IMPLEMENTED CANDIDATE / NO EFFECT AUTHORITY
BOUNDED PILOT RUNTIME: IMPLEMENTED CANDIDATE / TWO HISTORICAL REVIEWED DRAFT-PR OUTPUTS EXIST
GENERIC EXTERNAL PROJECT EXECUTION: FORBIDDEN
BOUNDED PILOT REPOSITORIES: EXACTLY TWO / DRAFT PR ONLY
AUTO MERGE: DISABLED

P4: NOT CLAIMED
INDEPENDENT PHASE C: REQUIRED AFTER FRESH NEW CONSEQUENTIAL EVIDENCE
FINAL HUMAN ACCEPTANCE: OPEN / NOT AVAILABLE YET
```
