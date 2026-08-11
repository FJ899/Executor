# Creative OS Executor

Repozytorium: `JTJ07/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Executor jest runtime wykonawczym większego systemu Creative OS. Otrzymuje zatwierdzony kierunek i zamienia go w odwracalne, testowalne działanie. Nie zastępuje Ginsenga ani warstw deliberacyjnych, których rolą jest wyjście poza pierwszą ramę użytkownika, odkrycie potencjału, porównanie wariantów i przygotowanie rekomendacji.

Executor nie jest właścicielem celu. Aktualny pierwszy produktowy pion to wykonanie dobrze określonego zadania technicznego w repozytorium i pokazanie zmiany wraz z weryfikacją.

Zabezpieczenia, sandbox i dowód są fundamentami uczciwego wykonania, ale nie stanowią głównego celu produktu.

Aktualny zakres implementacji fundamentów obejmuje:

- **M0 — Test Contract Validator**;
- **M1 — Project Contract + Policy Engine**;
- **M2A — State Machine + Checkpointy**;
- **M2B — Izolowany Sandbox dla fixtures**.

Sandbox używa backendu Docker bez fallbacku do wykonania na hoście. Profil wymusza: read-only root, read-only source, osobny tmpfs workspace, brak sieci, brak sekretów, niedostępny HOME, non-root, usunięte capabilities, limity CPU/RAM/dysku/procesów/czasu oraz cleanup po runie. Polityka, source, obraz i własność kontenera są wiązane z niezmiennymi identyfikatorami oraz weryfikowane fail-closed.

M2B jest zweryfikowany wyłącznie na fixtures należących do repo Executora. Uruchamianie kodu z COS, ScriptOps, BPM:160 i innych repozytoriów nadal jest zabronione.

## Start

```bash
python -m unittest discover -s tests -v
python -m compileall -q executor
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
- `CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md` — zasady pracy i audytu.

Otwarty draft PR, branch-only dokument albo komentarz review nie zmienia kanonu `main` przed merge.

## Action Authorization Packet

Action Authorization Packet jest zamrożonym kontraktem semantycznym i posiada walidator na `main`.

Poprawny pakiet oznacza wyłącznie:

```text
READY_FOR_ATOMIC_CONSUMPTION
```

Nie jest dowodem wykonania. Atomowy ledger konsumpcji i związanie wyniku akcji nie są obecnie claimowane jako wdrożone na `main`.

## Build status versus maturity

Po PR #42 rozdzielamy bieżący kierunek budowy od drabiny maturity.

```text
ARCHITECTURE / PRODUCT BUILD BASELINE: ACCEPTED
PR #42 MATURITY ADVANCEMENT: NONE
PR #42 RUNTIME IMPLEMENTATION CLAIM: NONE

CURRENT BUILD TARGET: GP001 — FIX A FAILING TEST VERTICAL PATH
NEXT BUILD ARTIFACT AFTER AUTHORITY RECONCILIATION: GP001 MACHINE-READABLE CONTRACT

CURRENT PROVEN PRODUCT LEVEL: P0 — FOUNDATION / ACHIEVED IN DECLARED SCOPE
P0 ACHIEVED SHA: b092a85e82eb81ec6dc7db4a7064409c6c383359
P0 EVIDENCE PR: #16
P0 EVIDENCE RUN ID: 30755381646
P0 HUMAN DECISION: ACCEPTED THROUGH MERGE OF PR #16

NEXT UNACHIEVED LADDER LEVEL: P1 — CONTROLLED PILOT RUNTIME
ACTIVE MATURITY CLAIM: NONE — ASSESS ONLY AFTER PRODUCT RUN
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
GP001 PRODUCT PATH: DEFINED / NOT YET END-TO-END IMPLEMENTED
POTENTIAL AND DECISION PACKET: LOGICAL CONTRACT / NOT IMPLEMENTED
ACTION AUTHORIZATION PACKET: CONTRACT FROZEN / VALIDATOR IMPLEMENTED / ATOMIC LEDGER NOT CLAIMED ON MAIN
WORK AND AUDIT PROTOCOL: DOCUMENTED / RUNTIME ENFORCEMENT NOT CLAIMED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
```
