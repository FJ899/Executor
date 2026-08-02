# Executor Pilot Target Selection v1.0

## Status

```text
PROJECT 0: TARGET AND CASES PREPARED
BASELINE ACCEPTANCE: PENDING HUMAN REVIEW AND MERGE
EXECUTOR INTEGRATION: NOT STARTED
PRODUCT VALUE VALIDATION: NOT STARTED
```

Ten dokument zapisuje wynik pierwszego działania z planu `EXECUTOR_MVP_REMEDIATION_AND_VALIDATION_PLAN_v1.0.md`. Nie jest dowodem ukończenia MVP ani dowodem wartości produktu.

## Wybrany cel techniczny

```text
repository: litrgratis-pixel/executor-pilot-target
purpose: controlled technical benchmark
language: Python >=3.11
runtime dependencies: none
network: forbidden
secrets: none
canonical test command: python -m unittest discover -s tests -v
compile command: python -m compileall -q project_registry tests
```

Repo zostało utworzone jako odrębny poligon, aby Executor nie definiował zadania, implementacji, testu i werdyktu we własnym repozytorium.

## Granica dowodu

Poligon może potwierdzić:

- utworzenie bezpiecznej gałęzi lub worktree;
- przestrzeganie dozwolonych ścieżek;
- wykonanie rzeczywistego workera;
- uruchomienie testów w sandboxie;
- zwrot diffu, komend, logów i statusu;
- brak bezpośredniego merge;
- odtworzenie runu od przypiętego commita.

Poligon nie może potwierdzić:

- że Executor rozwiązuje wartościowy problem użytkownika;
- że oszczędza pracę na realnym projekcie;
- że wynik jest lepszy od zwykłego coding agenta;
- że można zamknąć `FIN-008`;
- że M3, holdout lub terminalny `PASS` są potrzebne.

## Poprawna baza referencyjna

```text
branch: agent/bootstrap-pilot-target
commit: be1de04a1dbac7aac2d541b48cb252e1d72e4b7d
pull request: litrgratis-pixel/executor-pilot-target#1
status: DRAFT
```

Baza zawiera:

- pakiet `project_registry`;
- 13 testów;
- CLI do kanonizacji JSON;
- trzy jawne kontrakty przypadków;
- `PILOT_CONTRACT.md`;
- GitHub Actions z `compileall` i pełnym zestawem testów.

## Dowód poprawności bazy

Lokalna walidacja odtworzonego snapshotu:

```text
python -m compileall -q project_registry tests
OK

python -m unittest discover -s tests -v
Ran 13 tests
OK
```

GitHub Actions:

```text
workflow: pilot-target-ci
run_id: 30758465712
conclusion: success
```

Baza nie zostaje uznana za kanoniczną, dopóki draft PR #1 nie przejdzie przeglądu człowieka i nie zostanie świadomie scalony.

## Przypięte przypadki

### CASE-001 — atomowy batch

```text
branch: case-001-broken
commit: 3934a94a5eebf750079200589d6dc40e024d44a0
issue: litrgratis-pixel/executor-pilot-target#2
allowed path: project_registry/registry.py
observed failure count: 1
```

Obserwowana porażka:

```text
FAIL: test_duplicate_batch_does_not_partially_mutate_registry
```

Wymagany wynik: walidacja całego batcha przed mutacją i brak częściowego zapisu.

### CASE-002 — wznowienie zamkniętego projektu

```text
branch: case-002-broken
commit: c3683bf37ad6a3f1d49c0ca05ebdd41627e9a5be
issue: litrgratis-pixel/executor-pilot-target#3
allowed path: project_registry/registry.py
observed failure count: 1
```

Obserwowana porażka:

```text
FAIL: test_closed_project_requires_reason_before_reopening
```

Wymagany wynik: `CLOSED -> ACTIVE` wymaga niepustego `reopen_reason`.

### CASE-003 — deterministyczny JSON

```text
branch: case-003-broken
commit: c42bead2bbbff9c84486f17637ec80f35eeffa25
issue: litrgratis-pixel/executor-pilot-target#4
allowed path: project_registry/registry.py
observed failure count: 2
```

Obserwowane porażki:

```text
FAIL: test_different_input_order_produces_identical_stdout
FAIL: test_json_output_is_sorted_stable_and_utf8_friendly
```

Obie porażki dotyczą jednej własności: wynik zależy od kolejności wejścia.

## Niezmienniki wykonania

Każde zadanie Executora musi:

1. rozpocząć się od dokładnego commita przypadku;
2. utworzyć nową gałąź lub worktree;
3. pozwolić zmienić wyłącznie `project_registry/registry.py`;
4. zakazać zmian `tests/**`, `cases/**`, `PILOT_CONTRACT.md`, CI i konfiguracji;
5. uruchomić `compileall` oraz wszystkie 13 testów;
6. zwrócić pełny diff i log komend;
7. nie modyfikować gałęzi `case-*`;
8. nie wykonywać auto-merge;
9. zakończyć statusem `ACTION_COMPLETED_REVIEW_REQUIRED`, a nie terminalnym `PASS`;
10. pozostawić decyzję człowiekowi.

## Kolejność użycia

```text
1. Przejrzeć i świadomie scalić bazę targetu.
2. Dodać do Executora minimalny kontrakt zewnętrznego repo.
3. Uruchomić CASE-001 deterministycznym workerem.
4. Dopiero po poprawnym pełnym przepływie uruchomić CASE-002 i CASE-003.
5. Następnie podłączyć dokładnie jednego realnego workera AI.
6. Po zaliczeniu poligonu przejść do prawdziwego pilota w creative-os-project-reconstructor.
```

Nie wolno równolegle rozbudowywać M3, nowych providerów, GUI, wielu agentów ani kolejnych typów działań.

## Wpływ na ryzyka FIN

| Ryzyko | Status po przygotowaniu targetu | Uzasadnienie |
|---|---|---|
| `FIN-001` brak ostrego MVP | `PARTIAL` | istnieje jedno zdanie 1.0 i jeden typ zadania, ale runtime jeszcze go nie wykonuje |
| `FIN-002` brak domkniętego use case | `PARTIAL` | wejścia i kryteria są gotowe, brak wykonania przez Executor |
| `FIN-003` architektura wyprzedza potrzeby | `OPEN` | target nie usuwa zbędnej architektury Executora |
| `FIN-004` zbyt wczesne abstrahowanie | `OPEN` | nie przeprowadzono jeszcze uproszczenia runtime |
| `FIN-005` platforma zamiast rozwiązania | `PARTIAL` | zakres pilota jest zamknięty, ale produkt jeszcze nie został do niego ograniczony |
| `FIN-006` roadmapa bez końca | `PARTIAL` | istnieją bramki STOP, lecz nie zostały jeszcze użyte |
| `FIN-007` rozproszenie kierunków | `PARTIAL` | wybrano jedną ścieżkę pilota, pozostałe prace wymagają faktycznego zamrożenia |
| `FIN-008` brak dowodów użycia | `OPEN` | poligon techniczny nie jest realnym użyciem |

Żadne ryzyko nie otrzymuje statusu `ELIMINATED` na podstawie utworzenia tego repozytorium.

## Następna bramka

```text
CONTINUE, jeżeli:
- baza targetu jest zielona i zaakceptowana;
- Executor potrafi odczytać przypięte zewnętrzne repo bez rozszerzania zakresu;
- powstaje jeden pionowy przepływ CASE-001.

STOP, jeżeli:
- wykonanie CASE-001 wymaga najpierw nowych warstw M3;
- zespół próbuje dodać uniwersalny system adapterów;
- testy lub kontrakt muszą zostać zmienione, aby uzyskać zielony wynik;
- nie da się zwrócić prostego diffu i logu bez budowy kolejnego frameworka.
```
