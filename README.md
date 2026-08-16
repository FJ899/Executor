# Creative OS Executor

Repozytorium: `JTJ07/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Executor jest runtime wykonawczym większego systemu Creative OS. Otrzymuje zatwierdzony kierunek i zamienia go w odwracalne, testowalne działanie. Nie zastępuje Ginsenga ani warstw deliberacyjnych, których rolą jest wyjście poza pierwszą ramę użytkownika, odkrycie potencjału, porównanie wariantów i przygotowanie rekomendacji.

Executor nie jest właścicielem celu. Aktualny pierwszy produktowy pion to wykonanie dobrze określonego zadania technicznego w repozytorium i pokazanie zmiany wraz z weryfikacją.

Zabezpieczenia, sandbox i dowód są fundamentami uczciwego wykonania, ale nie stanowią głównego celu produktu.

Zakres na kanonicznym `main` obejmuje:

- **M0 — Test Contract Validator**;
- **M1 — Project Contract + Policy Engine**;
- **M2A — State Machine + Checkpointy**;
- **M2B — Izolowany Sandbox dla fixtures**.

Sandbox używa backendu Docker bez fallbacku do wykonania na hoście. Profil wymusza: read-only root, read-only source, osobny tmpfs workspace, brak sieci, brak sekretów, niedostępny HOME, non-root, usunięte capabilities, limity CPU/RAM/dysku/procesów/czasu oraz cleanup po runie. Polityka, source, obraz i własność kontenera są wiązane z niezmiennymi identyfikatorami oraz weryfikowane fail-closed.

Kandydat Phase B rozwija ten rdzeń bez włączania generycznego external execution. Polityka utrzymuje `external_projects: false` i dopuszcza wyłącznie dwa nazwane repozytoria pilotażowe, maksymalnie trzy pliki produkcyjne oraz draft PR bez merge. Dopóki implementacyjny PR nie zostanie zaakceptowany i scalony, jest to praca review-branch, a nie kanon `main`.

## Start

```bash
python -m unittest discover -s tests -v
python -m compileall -q executor
python -m executor.cli --help
python -m executor.cli validate-project project_contracts/executor-self.yaml --policy EXECUTOR_POLICY.yaml --base-dir .
python -m executor.cli validate-test test_contracts/examples/valid_test.yaml --base-dir tests/fixtures --holdout-evidence tests/fixtures/holdout_evidence.json
```

Pliki `.yaml` używają składni JSON, która jest poprawnym podzbiorem YAML 1.2.

## Jak czytać repo — źródła prawdy

`README.md` jest indeksem i skrótem statusu. Nie nadpisuje dedykowanych kontraktów.

- `docs/governance/DOCUMENT_AUTHORITY.md` — właścicielstwo źródeł prawdy i reguły rozstrzygania konfliktów;
- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md` — cel produktu i granice odpowiedzialności ekosystemu;
- `docs/product/EXECUTOR_V1_PRODUCT_SPEC.md` — pierwszy użyteczny produktowy pion i użytkownik v1;
- `docs/architecture/EXECUTOR_BUILD_MAP.md` — co architektonicznie budujemy;
- `docs/architecture/IMPLEMENTATION_INVENTORY.md` — datowany obraz tego, co faktycznie istnieje;
- `docs/EXECUTOR_BUILD_ORDER.md` — aktualna krytyczna kolejność budowy;
- `docs/product/GOLDEN_PATH_001_FIX_FAILING_TEST.md` — pierwszy Golden Path;
- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` — kanoniczne definicje poziomów maturity/proof, nie kolejka implementacyjna;
- `docs/philosophy/HUMAN_AI_DELIBERATION_MODEL.md` — przekrojowy model deliberacji, nie dowód;
- `ACTION_AUTHORIZATION_PACKET_v1.0.md` — zamrożony terminalny kontrakt autoryzacji konkretnej consequential action;
- `EXECUTOR_CHARTER.md` — misja Executora, hierarchia zaufania i warunki zatrzymania;
- `EXECUTOR_POLICY.yaml` — deterministyczna polityka wykonania;
- `CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md` — kontrakt implementacyjny;
- `CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md` — zasady pracy i audytu;
- `PHASE_B_AUTHORIZATION.md` — wybrane przez człowieka DONE, trust domain i granice pilotów;
- `docs/product/P4_GITHUB_PILOT_OPERATOR_GUIDE.md` — powtarzalny operator path i fail-closed states;
- `evidence/phase-c/PHASE_C_HANDOFF.md` — handoff dla niezależnej weryfikacji aktualnego kandydata.

Otwarty draft PR, branch-only dokument albo komentarz review nie zmienia kanonu `main` przed merge.

## Action Authorization Packet

Action Authorization Packet jest zamrożonym kontraktem semantycznym i posiada walidator na `main`.

Poprawny pakiet oznacza wyłącznie:

```text
READY_FOR_ATOMIC_CONSUMPTION
```

Nie jest dowodem wykonania. Kandydat Phase B dodaje trwały, atomowy ledger SQLite oraz dokładne związanie terminalnego wyniku. Claim pozostaje kandydatem do czasu pełnego exact-head evidence, endpoint-value review, niezależnej Phase C i finalnej decyzji człowieka.

## Build status versus maturity

Po PR #42 rozdzielamy bieżący kierunek budowy od drabiny maturity.

```text
ARCHITECTURE / PRODUCT BUILD BASELINE: ACCEPTED
PR #42 MATURITY ADVANCEMENT: NONE
PR #42 RUNTIME IMPLEMENTATION CLAIM: NONE

CURRENT HUMAN-SELECTED TARGET: P4 — REPEATABLE EXECUTOR 1.0
TRUST DOMAIN: GITHUB / EXTERNAL GOVERNED INTAKE
SOLUTION OWNER: EXTERNAL INTELLIGENCE
PILOT CLASS: JTJ07/scriptops + JTJ07/creative-os-project-reconstructor / DRAFT PR ONLY

CURRENT PROVEN PRODUCT LEVEL: P0 — FOUNDATION / ACHIEVED IN DECLARED SCOPE
P0 ACHIEVED SHA: b092a85e82eb81ec6dc7db4a7064409c6c383359
P0 EVIDENCE PR: #16
P0 EVIDENCE RUN ID: 30755381646
P0 HUMAN DECISION: ACCEPTED THROUGH MERGE OF PR #16

ACTIVE MATURITY CLAIM: NONE — P4 REQUIRES ALL PROJECT_COMPLETION_MAP GATES, INDEPENDENT PHASE C AND FINAL HUMAN ACCEPTANCE
FIRST TRUE PRODUCT MVP IN LADDER: P3 — REAL VALUE MVP
```

`v1` w nazwie `EXECUTOR_V1_PRODUCT_SPEC.md` oznacza wersję pierwszego product slice. Nie oznacza `P4 — REPEATABLE EXECUTOR 1.0` ani produkcyjnej gotowości.

Techniczny wynik testu lub wewnętrzny stan `PASS` nie oznacza automatycznie `PRODUCT ACCEPTED`, `HUMAN ACCEPTED`, `MERGED` ani osiągnięcia poziomu maturity.

## Status implementacji

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B: IMPLEMENTED / FIXTURES VERIFIED
M3+: NOT CLAIMED ON MAIN
PRODUCT PURPOSE: USER APPROVED / DOCUMENTED
BUILD BASELINE: ACCEPTED THROUGH PR #42
GP001 PRODUCT PATH: REAL FIXTURE E2E + REPLAY ACCEPTED IN DECLARED SCOPE
REQUEST TO CONTRACT: PHASE 1 IMPLEMENTED / CLI SURFACE IN PHASE B CANDIDATE
GITHUB REQUEST + DECISION TRUST: IMPLEMENTED CANDIDATE / REAL DIRECT-HUMAN REQUEST + ACCEPT EVENTS OBSERVED
ACTION AUTHORIZATION PACKET: VALIDATOR + ATOMIC LEDGER + RESULT BINDING IMPLEMENTED CANDIDATE
EXTERNAL SOLUTION INTERFACE: IMPLEMENTED CANDIDATE / NO EFFECT AUTHORITY
BOUNDED PILOT RUNTIME: IMPLEMENTED CANDIDATE / TWO REAL DRAFT-PR RESULTS EXIST (SCRIPTOPS #8, RECONSTRUCTOR #4)
EXACT-CANDIDATE EVIDENCE: MUST BE RESOLVED FROM SUCCESSFUL WORKFLOW + ARTIFACTS FOR THE CURRENT PR #61 HEAD; DO NOT TRUST HISTORICAL HEAD LOCATORS
WORK AND AUDIT PROTOCOL: DOCUMENTED / RUNTIME ENFORCEMENT NOT CLAIMED
GENERIC EXTERNAL PROJECT EXECUTION: FORBIDDEN
BOUNDED PILOT REPOSITORIES: EXACTLY TWO / DRAFT PR ONLY
AUTO MERGE: DISABLED

P4: NOT CLAIMED
INDEPENDENT PHASE C: REQUIRED AGAINST THE CURRENT EXACT CANDIDATE HEAD
FINAL HUMAN ACCEPTANCE: OPEN
```
