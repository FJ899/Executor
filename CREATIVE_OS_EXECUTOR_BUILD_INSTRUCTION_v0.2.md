---
document: "Creative OS Executor — instrukcja implementacyjna"
version: "0.2"
status: "READY FOR FOUNDATION IMPLEMENTATION"
execution_lock: "EXTERNAL PROJECT EXECUTION FORBIDDEN UNTIL M0-M3 PASS"
target_repository: "litrgratis-pixel/creative-os-executor"
first_pilot: "GINSENG_TEST-003"
audit_source: "CREATIVE_OS_EXECUTOR_AUDIT_v0.2.md"
---

# Creative OS Executor — instrukcja implementacyjna v0.2

## 0. Status dokumentu

Ta wersja zastępuje v0.1 jako kontrakt implementacyjny.

V0.1 pozostaje materiałem projektowym. Nie należy na jej podstawie rozpoczynać pełnego wykonania.

Do czasu zaliczenia Milestone 0–3 Executor może:

- walidować kontrakty;
- planować;
- generować syntetyczne testy własnych mechanizmów;
- pracować na fixtures znajdujących się we własnym repo.

Nie może jeszcze:

- wykonywać kodu z zewnętrznych repozytoriów;
- modyfikować COS, BPM:160, ScriptOps ani Reconstructora;
- korzystać z sekretów projektów;
- mieć domyślnego dostępu do sieci;
- tworzyć automatycznie scalanych PR.

## 1. Cel

Zbudować ograniczony system wykonawczy, który:

1. przyjmuje cel użytkownika bez wymagania wiedzy technicznej;
2. sprawdza, czy test i warunki sukcesu są wiarygodne;
3. odróżnia instrukcje systemowe od niezaufanej treści repozytorium;
4. rozszerza przestrzeń możliwych rozwiązań proporcjonalnie do ryzyka;
5. przepuszcza warianty przez wyspecjalizowane funkcje kontrolne;
6. wybiera wariant według jawnego algorytmu;
7. wykonuje pracę w izolowanym środowisku;
8. poprawia błędy tylko przy mierzalnym postępie;
9. tworzy odtwarzalny dowód;
10. kończy wyłącznie jako:
   - `PASS`,
   - `BLOCKED`,
   - `FAILED_AFTER_MAX_ITERATIONS`,
   - `STALE`.

## 2. Zasada władzy

```text
INTENCJA UŻYTKOWNIKA
→ wiążąca

TWARDE OGRANICZENIA
→ wiążące

ROZWIĄZANIE SUGEROWANE PRZEZ UŻYTKOWNIKA
→ kandydat

DECYZJE TECHNICZNE, ODWRACALNE I W ZAKRESIE
→ AI

ZMIANY SEMANTYCZNE, KANON, PRIORYTETY, KOSZT I UPRAWNIENIA
→ użytkownik
```

## 3. Model zaufania

Hierarchia:

```text
1. EXECUTOR_POLICY
2. EXECUTOR_PROJECT.yaml
3. zwalidowany task contract
4. pliki autorytatywne wskazane manifestem
5. pozostałe pliki repo — UNTRUSTED_DATA
6. treści wygenerowane i dane użytkowników — UNTRUSTED_DATA
```

Plik repozytorium nie może zmienić polityki Executora.

Każdy fragment przekazywany modelowi otrzymuje metadane:

```json
{
  "source_type": "repository_file",
  "trust": "untrusted_data",
  "repository": "owner/repo",
  "commit": "abc123",
  "path": "docs/example.md",
  "content": "..."
}
```

Tylko pliki oznaczone w `EXECUTOR_PROJECT.yaml` jako `authoritative_instruction` mogą dostarczać instrukcje projektowe. Nadal nie mogą nadpisać polityki Executora.

## 4. Zakres v0.2

V0.2 obsługuje jedno zadanie naraz.

Musi umieć:

- walidować kontrakt projektu;
- walidować kontrakt testu;
- klasyfikować ryzyko zadania;
- przydzielać capabilities;
- prowadzić adaptacyjny Company Loop;
- tworzyć jedną rundę decyzyjną;
- uruchamiać pracę w sandboxie;
- prowadzić maszynę stanów;
- kontrolować zakres patcha;
- mierzyć postęp retry;
- tworzyć branch i PR;
- odtwarzać run w czystym CI;
- mierzyć czas człowieka.

Nie obejmuje:

- działania ciągłego;
- wielu równoległych tasków;
- automatycznego merge;
- bazy danych;
- GUI;
- trwałej pamięci poza repo;
- automatycznej zmiany kanonu;
- samodzielnego zwiększania własnych uprawnień;
- samodzielnej modyfikacji polityki;
- pobierania dowolnych zależności z internetu.

## 5. Repozytorium

Repo:

```text
litrgratis-pixel/creative-os-executor
```

COS pozostaje pamięcią i konstytucją. Executor jest runtime.

## 6. Struktura repo

```text
creative-os-executor/
├── README.md
├── EXECUTOR_CHARTER.md
├── EXECUTOR_POLICY.yaml
├── pyproject.toml
├── uv.lock | requirements.lock
├── .env.example
├── .gitignore
│
├── executor/
│   ├── cli.py
│   ├── config.py
│   ├── errors.py
│   ├── state_machine.py
│   │
│   ├── contracts/
│   │   ├── project.py
│   │   ├── task.py
│   │   ├── test_contract.py
│   │   ├── capabilities.py
│   │   └── validator.py
│   │
│   ├── policy/
│   │   ├── engine.py
│   │   ├── path_rules.py
│   │   ├── change_impact.py
│   │   ├── objections.py
│   │   └── trust.py
│   │
│   ├── test_validation/
│   │   ├── controls.py
│   │   ├── oracle.py
│   │   ├── holdout.py
│   │   └── report.py
│   │
│   ├── company_loop/
│   │   ├── risk_classifier.py
│   │   ├── expansion.py
│   │   ├── deterministic_filter.py
│   │   ├── department_batch_review.py
│   │   ├── red_team.py
│   │   ├── scoring.py
│   │   ├── tie_break.py
│   │   └── board.py
│   │
│   ├── departments/
│   │   ├── strategy.py
│   │   ├── product.py
│   │   ├── technology.py
│   │   ├── operations.py
│   │   ├── finance.py
│   │   ├── risk.py
│   │   └── qa.py
│   │
│   ├── sandbox/
│   │   ├── runner.py
│   │   ├── filesystem.py
│   │   ├── network.py
│   │   ├── resources.py
│   │   ├── commands.py
│   │   └── cleanup.py
│   │
│   ├── execution/
│   │   ├── preflight.py
│   │   ├── workspace.py
│   │   ├── planner.py
│   │   ├── implementer.py
│   │   ├── verifier.py
│   │   ├── retry.py
│   │   └── reporter.py
│   │
│   ├── evidence/
│   │   ├── manifest.py
│   │   ├── hashing.py
│   │   ├── diff.py
│   │   ├── replay.py
│   │   └── provenance.py
│   │
│   ├── adapters/
│   │   ├── model.py
│   │   ├── github.py
│   │   ├── process.py
│   │   └── clock.py
│   │
│   └── metrics/
│       ├── machine.py
│       ├── human.py
│       └── benchmark.py
│
├── schemas/
│   ├── executor_project.schema.json
│   ├── task.schema.json
│   ├── test_contract.schema.json
│   ├── proposal.schema.json
│   ├── department_review.schema.json
│   ├── board_packet.schema.json
│   ├── run_checkpoint.schema.json
│   ├── run_manifest.schema.json
│   └── failure_record.schema.json
│
├── prompts/
│   ├── normalize.md
│   ├── expand.md
│   ├── department_*.md
│   ├── red_team.md
│   └── board.md
│
├── project_contracts/
│   ├── examples/
│   └── executor-self.yaml
│
├── tasks/
│   ├── examples/
│   └── GINSENG_TEST-003.yaml
│
├── test_contracts/
│   ├── examples/
│   └── GINSENG_TEST-003.test.yaml
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── regression/
│   ├── fixtures/
│   └── holdout/
│
├── runs/
│   └── .gitkeep
│
└── .github/workflows/
    ├── verify.yml
    ├── replay.yml
    └── execute-task.yml
```

## 7. Kontrakt projektu

Każdy projekt musi dostarczyć `EXECUTOR_PROJECT.yaml`.

Przykład:

```yaml
schema_version: executor-project/1.0

project:
  name: Creative OS
  repository: litrgratis-pixel/COS
  entrypoint: START_HERE.md

authoritative_sources:
  - path: START_HERE.md
    role: authoritative_instruction
  - path: CREATIVE_OS.md
    role: state_owner

commands:
  setup: []
  unit_test: []
  integration_test: []
  full_verify:
    - python scripts/verify_creative_os.py

path_rules:
  "CREATIVE_OS.md":
    class: semantic
    approval: USER
  "projects/**":
    class: semantic
    approval: USER
  "scripts/**":
    class: technical
    approval: AI
  ".github/workflows/**":
    class: infrastructure
    approval: USER
  "**":
    class: unknown
    approval: USER

change_impact_rules:
  public_api_change: USER
  data_schema_change: USER
  result_semantics_change: USER

capabilities:
  network:
    default: false
  secrets:
    default: []
  commands:
    allow:
      - python
      - git
  dependencies:
    install: locked_only

environment:
  python: "3.11"
  max_cpu: 2
  max_memory_mb: 4096
  max_disk_mb: 2048
  timeout_minutes: 30
  home_access: false

artifacts:
  output: artifacts/**
  baseline: baselines/**

rollback:
  strategy: git_reset

owners:
  semantic_changes: USER
  technical_changes: AI
  infrastructure_changes: USER
```

Brak manifestu oznacza `PROJECT_NOT_ONBOARDED`.

## 8. Kontrakt zadania

Task zawiera:

- cel;
- zakres;
- klasę ryzyka;
- capabilities;
- repo i commity;
- wejścia i hashe;
- dozwolone klasy zmian;
- test contract;
- budżety;
- warunki zatrzymania;
- politykę decyzji;
- politykę merge.

Przykład:

```yaml
schema_version: executor-task/1.0

id: GINSENG_TEST-003
risk_class: HIGH_RISK
mode: BUILD_AND_TEST

repositories:
  control:
    name: litrgratis-pixel/COS
    commit: LOCKED_SHA
  target:
    name: litrgratis-pixel/creative-os-executor
    commit: LOCKED_SHA

test_contract:
  path: test_contracts/GINSENG_TEST-003.test.yaml
  sha256: LOCKED_HASH

capabilities:
  network: false
  secrets: []
  commands:
    - python
    - git

budgets:
  max_model_calls: 40
  max_execution_iterations: 4
  max_wall_time_minutes: 90
  max_patch_lines: 1200

decision_policy:
  max_decision_rounds: 1

merge_policy:
  mode: PR_ONLY
```

## 9. Test Contract Validation

Test contract jest walidowany przed pierwszym wywołaniem modelu.

Wymagane pola:

```yaml
schema_version: executor-test/1.0

test_id: GINSENG_TEST-003

source_claims:
  - claim: blocking_gate_count_before == 7
    source:
      file: S001_test2_result.json
      selector: $.blocking_gate_count

positive_control:
  description: właściwa decyzja zamyka bramkę reklamacji

negative_control:
  description: brak decyzji pozostawia 7 bramek

tamper_control:
  description: ręczna zmiana result.json bez replay runnera ma zostać wykryta

unchanged_controls:
  - pięć NO_IMPACT pozostaje bez zmian
  - baseline hash pozostaje bez zmian
  - sześć pozostałych bramek zachowuje znaczenie

holdout:
  visibility: HIDDEN_FROM_IMPLEMENTER
  location: tests/holdout/GINSENG_TEST-003_HOLDOUT.enc

acceptance:
  - blocking_gate_count_after == 6
  - baseline_mutated_after == false
  - implementation_readiness_after == BLOCKED
```

Walidator sprawdza:

- kompletność;
- sprzeczności;
- pochodzenie oczekiwań;
- obecność kontroli;
- zdolność wykrycia braku implementacji;
- zdolność wykrycia manipulacji;
- niezależność holdoutu.

Wyniki:

```text
VALID
INVALID
INSUFFICIENT_EVIDENCE
```

`INVALID` i `INSUFFICIENT_EVIDENCE` zatrzymują task przed modelem.

## 10. Typy sprzeciwu

```text
HARD_VETO
POLICY_VETO
EVIDENCE_GAP
CONCERN
PASS
```

### HARD_VETO

Tworzone wyłącznie przez policy engine albo kontrolę deterministyczną.

### POLICY_VETO

Naruszenie polityki projektu. Wymaga zmiany wariantu albo decyzji właściciela.

### EVIDENCE_GAP

Brakuje dowodu, lecz naruszenie nie zostało potwierdzone.

### CONCERN

Ryzyko nieblokujące.

Model może proponować klasyfikację, ale kod zatwierdza możliwość `HARD_VETO`.

## 11. Adaptacyjny Company Loop

### 11.1. Klasa ryzyka

```text
LOW_RISK
MEDIUM_RISK
HIGH_RISK
```

Przykładowe kryteria wysokiego ryzyka:

- wykonywanie nieznanego kodu;
- zmiana semantyczna;
- dostęp do sieci;
- dostęp do sekretu;
- zmiana formatu danych;
- wysokie koszty;
- publikacja;
- brak rollbacku;
- test decydujący o kierunku produktu.

### 11.2. Szerokość

```text
LOW_RISK       2–3 kandydatów
MEDIUM_RISK    4–6 kandydatów
HIGH_RISK      8–12 kandydatów
```

### 11.3. Obieg

```text
NORMALIZE
→ EXPAND
→ DETERMINISTIC PREFILTER
→ maksymalnie 4 kandydatów
→ 7 batch reviews
→ POLICY FILTER
→ RED TEAM
→ maksymalnie 2 kandydatów
→ MICROEXPERIMENT przy remisie
→ BOARD
```

Każdy dział ocenia wszystkie pozostałe warianty w jednym wywołaniu.

Działy nie widzą ocen innych działów przed Board.

## 12. Algorytm Board

1. usuń `HARD_VETO`;
2. usuń warianty poniżej `minimum_proofability`;
3. zastosuj wagi dla klasy zadania;
4. wybierz najwyższy wynik;
5. jeżeli różnica jest mniejsza niż `tie_threshold`, uruchom mikroeksperyment;
6. wybierz wynik eksperymentu;
7. sprawdź `POLICY_VETO`;
8. utwórz Board Packet;
9. utwórz maksymalnie jedną rundę decyzyjną.

Board nie tworzy nowego wariantu.

Override wymaga:

```yaml
override:
  reason:
  evidence:
  accepted_by:
```

## 13. Jedna runda decyzyjna

Board zwraca jeden pakiet:

```text
DECISION ROUND
1. decyzja A — TAK/NIE
2. decyzja B — TAK/NIE
3. koszt — limit
```

Pakiet zawiera tylko pytania konieczne do dalszego ruchu.

Brak odpowiedzi oznacza `AWAITING_DECISION`, nie zgadywanie.

## 14. Sandbox

Minimalne wymagania:

- jednorazowe środowisko;
- czysty checkout wskazanego SHA;
- źródła read-only;
- writable workspace;
- sieć off;
- sekrety none;
- HOME niedostępny;
- allowlista komend;
- instalacja tylko z lockfile;
- limit CPU;
- limit RAM;
- limit dysku;
- timeout;
- pełny log procesu;
- cleanup po runie.

Zdolności są przyznawane per task.

Próba użycia niedozwolonej zdolności tworzy `HARD_VETO`.

## 15. Maszyna stanów

```text
CREATED
CONTRACT_VALIDATED
NORMALIZED
PLANNED
AWAITING_DECISION
APPROVED
EXECUTING
VERIFYING
REPLAYING
PASS
BLOCKED
FAILED
STALE
```

Każdy checkpoint zapisuje:

```text
executor_version
policy_version
project_contract_hash
task_contract_hash
test_contract_hash
prompt_bundle_hash
model_id
repository_shas
input_hashes
workspace_hash
```

### Resume

```text
resume
→ REVALIDATE
→ unchanged: continue
→ changed: STALE
```

Run `STALE` może zostać:

- sklonowany do nowego runu;
- ponownie zaplanowany;
- zamknięty.

Nie może być kontynuowany bezpośrednio.

## 16. Execution Loop

### Preflight

- kontrakty;
- SHA;
- capabilities;
- dostęp;
- baseline;
- test baseline;
- sandbox;
- policy.

### BEFORE

- repo SHAs;
- wejścia;
- testy bazowe;
- metryki;
- protected paths;
- baseline hash.

### Plan

- pliki;
- kolejność;
- test przed kodem;
- oczekiwana delta;
- rollback;
- limit patcha.

### Implement

- tylko zakres kontraktu;
- brak ręcznej edycji artefaktów jako mechanizmu PASS;
- brak osłabiania testu;
- brak niezatwierdzonych zależności.

### Verify

- unit;
- integration;
- full verify;
- acceptance;
- protected paths;
- baseline;
- provenance;
- tamper control.

## 17. Retry z miernikiem postępu

Każda iteracja:

```json
{
  "iteration": 2,
  "error_fingerprint": "...",
  "tests_passed_before": 18,
  "tests_passed_after": 21,
  "new_failures": 0,
  "changed_files": 3,
  "patch_size_lines": 84,
  "acceptance_delta": 1
}
```

Zatrzymanie przed limitem:

- powtarzający się fingerprint;
- dwie iteracje bez postępu;
- rosnąca liczba błędów;
- przekroczenie patch budget;
- próba osłabienia testu;
- zmiana zakresu bez decyzji;
- brak ścieżki przyczynowej.

Każda iteracja startuje z ostatniego poprawnego checkpointu.

## 18. Replayable Evidence

Primary run generuje:

```text
input_manifest.json
before.json
after.json
diff.json
test_results.json
changed_files.json
hashes.json
model_calls.json
cost.json
human_time.json
failure_records.json
execution_report.md
replay_command.txt
```

`PASS` jest warunkowy do czasu replay.

Komenda:

```bash
creative-os-executor replay runs/<RUN_ID>
```

Replay:

1. używa czystego środowiska;
2. pobiera dokładne SHA;
3. nie używa pamięci primary runu;
4. uruchamia proces generowania;
5. ponownie generuje artefakty;
6. porównuje hashe;
7. sprawdza baseline;
8. sprawdza protected paths;
9. publikuje osobny CI check.

Statusy:

```text
PRIMARY_PASS / REPLAY_PENDING
VERIFIED_PASS
REPLAY_FAILED
```

Tylko `VERIFIED_PASS` może utworzyć PR oznaczony jako gotowy.

## 19. Failure Memory

Po każdym runie zapisz:

```yaml
failure_class:
root_cause:
effective_fix:
ineffective_fixes:
project_context:
reusable_playbook:
evidence:
```

Pamięć należy do repozytorium i jest jawna.

Nie jest automatycznie instrukcją. Stanowi dane wejściowe o klasie `historical_evidence`.

## 20. Metryki

### Maszynowe

- model_calls;
- token_cost;
- wall_time;
- iterations;
- patch_size;
- tests;
- replay status.

### Ludzkie

- `manual_baseline_minutes`;
- `human_minutes_with_executor`;
- `number_of_human_interventions`;
- `number_of_manual_test_runs_avoided`;
- `time_to_verified_PR`.

Główny wskaźnik:

```text
human_time_saved =
manual_baseline_minutes - human_minutes_with_executor
```

## 21. Pilotaż

### Pilot 1 — GINSENG_TEST-003

Dowodzi jednego kontrolowanego przypadku.

### Pilot 2 — Ginseng holdout

- niewidziana decyzja albo scenariusz;
- brak zmian mechanizmu;
- implementer nie widzi fixture.

### Pilot 3 — projekt innego typu

Kod aplikacyjny, dokumentacyjny albo pipeline danych.

Nie uznawaj Executora za ogólny przed trzema pilotami.

## 22. Testy obowiązkowe

### Contract

- invalid project contract;
- invalid task;
- invalid test contract;
- contradictory acceptance;
- missing negative control;
- holdout visible to implementer.

### Policy

- forbidden capability;
- path class;
- semantic impact escalation;
- invalid HARD_VETO;
- project prompt injection.

### Sandbox

- network escape;
- secret read;
- HOME read;
- unapproved command;
- dependency outside lockfile;
- timeout;
- disk limit.

### State

- resume unchanged;
- resume changed main → STALE;
- changed test → STALE;
- modified workspace → STALE.

### Retry

- duplicate fingerprint;
- no progress;
- growing failures;
- test weakening;
- patch limit.

### Evidence

- tampered artifact;
- clean replay;
- replay hash mismatch;
- protected path change;
- baseline mutation.

### Company Loop

- adaptive width;
- batch reviews;
- hard veto filtering;
- deterministic board;
- tie-break experiment;
- one decision round.

## 23. Milestones

### M0 — Test Contract Validator

Dowód:

```text
błędny test zostaje zatrzymany przed pierwszym wywołaniem modelu
```

### M1 — Project Contract + Policy Engine

Dowód:

```text
twarde granice egzekwuje kod
```

### M2 — Sandbox + State Machine

Dowód:

```text
niezaufany kod i zmiana stanu nie omijają izolacji
```

### M3 — Replayable Evidence

Dowód:

```text
wynik można odtworzyć bez pamięci primary runu
```

### M4 — Adaptive Company Loop

Dowód:

```text
wariant jest wybierany jawnie i w budżecie
```

### M5 — Execution + Retry

Dowód:

```text
naprawy dają mierzalny postęp albo run zatrzymuje się wcześniej
```

### M6 — Ginseng Test 003

### M7 — Ginseng Holdout

### M8 — Cross-domain Pilot

## 24. Definition of Done v0.2

Executor jest ukończony, gdy:

- M0–M5 przechodzą pełne testy;
- zewnętrzny projekt wymaga manifestu;
- test jest walidowany przed modelem;
- repo jest traktowane jako niezaufane dane;
- sandbox działa bez sieci i sekretów domyślnie;
- HARD_VETO jest deterministyczne;
- Board ma jawny algorytm;
- resume wykrywa stale state;
- retry mierzy postęp;
- dowód ma niezależny replay;
- trzy piloty są zakończone;
- mierzone są minuty człowieka;
- żaden run nie zapisuje bezpośrednio do main;
- automatyczny merge pozostaje wyłączony.

## 25. Czego nie budować przed M6

- dashboard;
- kolejka;
- scheduler;
- wiele modeli we wszystkich działach;
- pamięć wektorowa;
- globalny system pluginów;
- automatyczny merge;
- samonaprawa Executora;
- monitoring rozmów;
- wieloużytkownikowość.

## 26. Pierwsze polecenie implementacyjne

```text
Utwórz szkielet repozytorium creative-os-executor zgodnie z
CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md.

Wykonaj wyłącznie:

M0 — Test Contract Validator
M1 — Project Contract + Policy Engine

Nie wykonuj kodu z innych repozytoriów.
Nie podłączaj GitHub App.
Nie używaj sekretów.
Nie włączaj sieci w runtime testów.
Nie implementuj jeszcze Company Loop ani Execution Loop.

Po wykonaniu przedstaw:

1. drzewo repo;
2. schemat EXECUTOR_PROJECT.yaml;
3. schemat task contract;
4. schemat test contract;
5. policy engine;
6. klasy HARD_VETO / POLICY_VETO / EVIDENCE_GAP / CONCERN;
7. przykłady pozytywnej i negatywnej walidacji;
8. test prompt injection z pliku repo;
9. test zmiany forbidden path;
10. wyniki CI.

Każde twierdzenie o PASS musi wskazywać test i log.
Zatrzymaj się po M1.
```

# Koniec instrukcji
