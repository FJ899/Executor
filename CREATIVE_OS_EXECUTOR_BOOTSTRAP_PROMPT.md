# Bootstrap prompt — Creative OS Executor

Repozytorium zostało utworzone jako:

```text
litrgratis-pixel/creative-os-executor
```

Przeczytaj w całości:

1. `CREATIVE_OS_EXECUTOR_AUDIT_v0.2.md`
2. `CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md`

Wersja v0.2 zastępuje v0.1 jako kontrakt implementacyjny.

## Zlecenie

Wykonaj tylko:

```text
M0 — Test Contract Validator
M1 — Project Contract + Policy Engine
```

## Twarde ograniczenia

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

## Wymagany wynik M0

- `test_contract.schema.json`;
- walidacja pozytywnego control;
- walidacja negatywnego control;
- tamper control;
- unchanged control;
- kontrakt holdoutu;
- wykrywanie sprzecznych kryteriów;
- status `BLOCKED_BEFORE_MODEL` dla błędnego testu.

## Wymagany wynik M1

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

## Raport końcowy

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
