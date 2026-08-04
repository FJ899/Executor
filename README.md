# Creative OS Executor

Repozytorium: `litrgratis-pixel/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Executor jest systemem kontrolowanego wykonania zmian w repozytorium. Otrzymuje kompletny, zatwierdzony kontrakt zadania, wykonuje pracę w określonych granicach, zbiera odtwarzalne evidence i zwraca draft PR wymagający decyzji człowieka.

Executor nie wybiera celu, nie prowadzi strategii, nie akceptuje własnego wyniku i nie jest autonomicznym właścicielem projektu. Jego kanoniczny kontrakt wejścia, przepływu, wyjścia, statusów oraz Definition of Done P3 zawiera `EXECUTOR_PRODUCT_CONTRACT_v1.0.md`.

Szerszy kontekst Creative OS oraz role Ginsenga i Company Loop opisuje `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`. Dokument ten nie rozszerza granicy wykonawczej Executora ani nie odblokowuje funkcji odłożonych poza P3.

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

## Dokumenty sterujące

- `EXECUTOR_PRODUCT_CONTRACT_v1.0.md` — kanoniczny kontrakt Executora: kompletne wejście, przepływ P3, draft PR, evidence, trzy terminalne statusy i granica decyzji człowieka;
- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` — kanoniczna drabina poziomów produktu, poziome osie dojrzałości, bramki i reguła odrzucania bocznych odnóg;
- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md` — szerszy cel ekosystemu oraz role Ginsenga, Company Loop, Creative OS, Executora i audytu;
- `EXECUTOR_CHARTER.md` — misja Executora, hierarchia zaufania i warunki zatrzymania;
- `EXECUTOR_POLICY.yaml` — deterministyczna polityka wykonania;
- `CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md` — kontrakt implementacyjny;
- `CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md` — zaakceptowane zasady autonomicznej pracy, rozmowy, pełnych instrukcji oraz audytu dowodowego;
- `ACTION_AUTHORIZATION_PACKET_v1.0.md` — zamrożony terminalny kontrakt jednorazowej autoryzacji konkretnego działania.

Protokół pracy i audytu jest obowiązującym źródłem instrukcji dla projektu `executor-self`. Jego obecność nie jest dowodem implementacji mechanizmów runtime; egzekwowanie każdej reguły wymaga osobnego testu.

Action Authorization Packet jest zamrożonym kontraktem semantycznym i posiada walidator. Poprawny pakiet oznacza wyłącznie `READY_FOR_ATOMIC_CONSUMPTION`. Nie jest dowodem wykonania. Atomowy ledger konsumpcji i związanie wyniku akcji należą do projektu M3.

Kontrakt produktu jest zatwierdzoną decyzją semantyczną. Nie stanowi dowodu implementacji P1, workera AI, P3, Ginsenga, Company Loop, `POTENTIAL_AND_DECISION_PACKET` ani M3.

## Kontrakt wyniku

Executor może zakończyć wykonanie wyłącznie jednym statusem:

```text
ACTION_COMPLETED_REVIEW_REQUIRED
BLOCKED
FAILED
```

Executor nie zwraca jako własnego wyniku `MERGED`, `ACCEPTED` ani `PRODUCT PASS`. Human Review i Human Decision znajdują się poza granicą Executora.

Autorytatywne evidence musi być zebrane albo zapieczętowane poza kontrolą wykonawcy zadania. Kandydacki `PASS`, raport wykonawcy i jego własne logi nie mogą samodzielnie zatwierdzić wyniku.

## Poziom produktu

```text
CURRENT MAIN PRODUCT LEVEL: P0 — FOUNDATION / ACHIEVED IN DECLARED SCOPE
P0 ACHIEVED SHA: b092a85e82eb81ec6dc7db4a7064409c6c383359
P0 EVIDENCE PR: #16
P0 EVIDENCE RUN ID: 30755381646
P0 HUMAN DECISION: ACCEPTED THROUGH MERGE OF PR #16
CURRENT TARGET: P1 — CONTROLLED PILOT RUNTIME
NEXT AFTER P1: P2 — AI WORKER MVP
FIRST TRUE PRODUCT MVP: P3 — REAL VALUE MVP
P3 PILOT CONTRACT-001: NOT SELECTED
M3: T3 TRUST AXIS / LOCKED UNTIL P3 PRODUCT DECISION CONTINUE
COMPANY LOOP: TARGETED AT P5
```

Pełne definicje, dowody i non-goals zawiera `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`. Kontrakt P3 oraz granice odpowiedzialności Executora zawiera `EXECUTOR_PRODUCT_CONTRACT_v1.0.md`.

## Status

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B: IMPLEMENTED / FIXTURES VERIFIED
M3+: LOCKED
EXECUTOR PRODUCT CONTRACT: USER APPROVED / FROZEN v1.0
P3 PILOT CONTRACT-001: NOT SELECTED
POTENTIAL AND DECISION PACKET: LOGICAL CONTRACT / NOT IMPLEMENTED
ACTION AUTHORIZATION PACKET: CONTRACT FROZEN / VALIDATOR IMPLEMENTED / LEDGER PENDING M3
WORK AND AUDIT PROTOCOL: DOCUMENTED / RUNTIME ENFORCEMENT NOT CLAIMED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
EXECUTOR SELF-ACCEPTANCE: FORBIDDEN
```
