---
document: "Creative OS Executor historical bootstrap prompt"
status: "HISTORICAL / SUPERSEDED / NOT CURRENT BOOTSTRAP"
reconciled_at: "2026-08-21"
historical_source_ref: "JTJ07/Executor@d6a9df0567dd37b3b6f997ba49cd23b4585c3a5a:CREATIVE_OS_EXECUTOR_BOOTSTRAP_PROMPT.md"
current_recovery_entry: "README.md"
---

# Bootstrap prompt — Creative OS Executor

## CURRENT RECOVERY NOTICE

This file is retained as historical bootstrap provenance. It is **not** a current implementation route and must not be used to restart M0/M1 or select M2 as the next step.

For a zero-history current recovery, read instead:

1. `README.md`;
2. `docs/governance/DOCUMENT_AUTHORITY.md`;
3. `docs/governance/EXECUTOR_1_0_FINAL_HUMAN_ACCEPTANCE_RECORD_2026-08-20.md`;
4. `docs/governance/HUMAN_INTERACTION_CONTRACT_POINTER.md`.

This current recovery sequence is complete only after step 4. Do not stop after product-state recovery without loading the current Human interaction contract pointer.

Current terminal facts are:

```text
REPOSITORY: JTJ07/Executor
EXECUTOR 1.0: HUMAN ACCEPTED
SELECTED ENDPOINT: P4 REPEATABLE EXECUTOR 1.0
G-01–G-18: PASS
ACTIVE PRODUCT COMPLETION GATE: NONE
NEW PRODUCT-DEVELOPMENT PHASE: NOT AUTHORIZED BY THIS FILE
```

The exact historical text below is preserved for provenance only.

---

## HISTORICAL BOOTSTRAP CONTENT — SUPERSEDED

Repozytorium zostało utworzone jako:

```text
litrgratis-pixel/Executor
```

Robocza nazwa projektu i pakietu Python pozostaje `creative-os-executor`. Nie jest to nazwa osobnego repozytorium.

Przeczytaj w całości:

1. `CREATIVE_OS_EXECUTOR_AUDIT_v0.2.md`
2. `CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md`

Wersja v0.2 zastępuje v0.1 jako kontrakt implementacyjny.

## Zlecenie historyczne

Wykonaj tylko:

```text
M0 — Test Contract Validator
M1 — Project Contract + Policy Engine
```

## Twarde ograniczenia historycznego bootstrapu

- nie wykonuj kodu z innych repozytoriów;
- nie modyfikuj repo `litrgratis-pixel/COS`;
- nie podłączaj GitHub App;
- nie używaj sekretów;
- sieć runtime testów ma być wyłączona;
- nie implementuj jeszcze Company Loop;
- nie implementuj jeszcze Execution Loop;
- nie twórz dashboardu, bazy danych ani kolejki;
- nie zapisuj bezpośrednio do `main`;
- wszystkie zmiany wykonuj przez branch i PR;
- nie osłabiaj testów w celu uzyskania PASS.

## Wymagany wynik M0 — historyczne

- `test_contract.schema.json`;
- walidacja pozytywnego control;
- walidacja negatywnego control;
- tamper control;
- unchanged control;
- kontrakt holdoutu;
- wykrywanie sprzecznych kryteriów;
- status `BLOCKED_BEFORE_MODEL` dla błędnego testu.

## Wymagany wynik M1 — historyczne

- `executor_project.schema.json`;
- przykładowy `EXECUTOR_PROJECT.yaml`;
- `EXECUTOR_POLICY.yaml`;
- policy engine;
- path classes;
- capability rules;
- trust model;
- klasy:
  - `HARD_VETO`,
  - `POLICY_VETO`,
  - `EVIDENCE_GAP`,
  - `CONCERN`;
- test, w którym tekst w pliku repo próbuje zmienić instrukcje Executora;
- test, w którym model proponuje `HARD_VETO` bez dowodu;
- test modyfikacji forbidden path;
- test żądania niedozwolonej sieci lub sekretu.

## Raport końcowy — historyczne

Przedstaw:

1. status wykonania;
2. drzewo repo;
3. listę plików;
4. kontrakty i wersje schematów;
5. listę testów;
6. wyniki CI;
7. elementy niewykonane;
8. błędy i retry;
9. obserwowalny dowód dla każdego PASS;
10. jeden następny krok: przygotowanie M2.

Nie pytaj o wybory techniczne, które są odwracalne i mieszczą się w zakresie.
Zatrzymaj się przy zmianie celu, zwiększeniu uprawnień albo potrzebie dostępu do danych zewnętrznych.
