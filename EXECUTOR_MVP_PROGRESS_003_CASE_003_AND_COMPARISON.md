# Executor MVP Progress 003 — CASE-003 and Three-Case Comparison

## Status

```text
CASE-001 TECHNICAL GATE: PASSED
CASE-002 TECHNICAL GATE: PASSED
CASE-003 TECHNICAL GATE: PASSED
CONTROLLED TECHNICAL BENCHMARK: COMPLETE
HUMAN ACCEPTANCE: PENDING
AI WORKER: NOT USED
PRODUCT VALUE VALIDATION: NOT STARTED
FIN-008: OPEN
```

Ten dokument kończy kontrolowany etap deterministyczny. Nie jest zgodą na utworzenie CASE-004 ani na scalenie eksperymentalnego stacku w obecnej postaci.

## CASE-003

```text
target repository: litrgratis-pixel/executor-pilot-target
input commit: c42bead2bbbff9c84486f17637ec80f35eeffa25
allowed path: project_registry/registry.py
Executor stacked draft PR: #26
verified runtime head: 3490d474dcc983e5104b9ca4cf56432486196756
workflow run: 30764964269
conclusion: success
```

Naprawa przywróciła kanoniczną kolejność projektów według `project_id`. Nie zmieniła `json.dumps`, UTF-8, końcowego znaku nowej linii, testów ani plików wejściowych.

Jeden workflow potwierdził:

- pełne foundation tests;
- 10/10 testów bezpieczeństwa sandboxu;
- realny CASE-001;
- realny CASE-002;
- realny CASE-003;
- `compileall` oraz pełne 13 testów każdego targetu;
- niezmienność trzech źródłowych checkoutów;
- cleanup wszystkich kontenerów.

## Porównanie przypadków

| Właściwość | CASE-001 | CASE-002 | CASE-003 |
|---|---|---|---|
| problem | nieatomowy batch | reopen bez uzasadnienia | niedeterministyczny JSON |
| przypięty commit | `3934a94...` | `c3683bf...` | `c42bead...` |
| zmieniany plik | `registry.py` | `registry.py` | `registry.py` |
| worker | dokładna zamiana fragmentu | dokładna zamiana fragmentu | dokładna zamiana fragmentu |
| wynik | 1 commit | 1 commit | 1 commit |
| komendy | compileall + 13 testów | compileall + 13 testów | compileall + 13 testów |
| sandbox | read-only source | read-only source | read-only source |
| status | review required | review required | review required |
| AI | nie | nie | nie |

## Co jest faktycznie wspólne

Trzy realne przebiegi potwierdzają ten sam mechaniczny rdzeń:

1. weryfikacja repozytorium, przypiętego commita i blobu kontraktu;
2. kontrola czystego źródła;
3. odrzucenie `runs_root` wewnątrz źródła;
4. utworzenie osobnego worktree i brancha;
5. wykonanie jednego ograniczonego workera;
6. kontrola dokładnie jednego dozwolonego pliku;
7. utworzenie jednego commita bez Git hooks i mechanizmów zewnętrznych;
8. sprawdzenie parenta i listy zmienionych ścieżek;
9. zapis patcha;
10. `compileall` i testy w sandboxie;
11. raport oraz status `ACTION_COMPLETED_REVIEW_REQUIRED`;
12. brak zmiany source checkoutu i cleanup kontenera.

## Co jest zmienne

Dla każdego zadania zmieniają się tylko:

- task ID;
- input commit;
- purpose;
- branch prefix;
- label kontenera;
- commit message;
- dokładny worker/transformacja;
- opcjonalne dodatkowe asercje wyniku.

To jest wystarczający dowód dla małego wspólnego rdzenia. Nie jest dowodem dla platformy adapterów, providerów, wielu agentów ani dowolnych typów działań.

## Koszt obecnej formy

Stack eksperymentalny zawiera trzy osobne pionowe implementacje. Sam CASE-003 dodał:

```text
353 linie case-specific runtime
168 linii testów jednostkowych
88 linii testu integracyjnego
70 linii rozszerzenia testów CLI
16 linii CI
124 linie dokumentacji
```

CASE-002 miał porównywalny koszt. Oznacza to, że kopiowanie kolejnych przypadków jest już udowodnioną złą ścieżką.

## Werdykt senior developer

```text
CONTROLLED BENCHMARK: PASS
CURRENT STACK AS PRODUCT CODE: BLOCKED
NEXT FEATURE: FORBIDDEN
NEXT ACTION: CONSOLIDATE AND DELETE
```

PR #23, #24 i #26 są wartościowym eksperymentem oraz dowodem. Nie powinny zostać scalone po prostu jeden po drugim w obecnej postaci.

## Następny planowany PR

Następny PR powinien być konsolidacyjny i oparty na dowodach z trzech przypadków. Jego jedynym celem jest:

```text
three duplicated pilot runtimes
→ one small pinned-task execution core
→ three tiny task specifications/workers
→ same three real Docker runs
→ fewer lines and no weaker boundary
```

### Do zachowania

- zahartowane wywołania Git bez hooków;
- pinned repository/commit/contract blob;
- clean source i external runs root;
- one worktree, one result commit;
- allowed paths;
- read-only Docker source;
- exact commands, logs, patch and report;
- source immutability and cleanup checks;
- review-required status.

### Do usunięcia lub zastąpienia

- trzy prawie identyczne funkcje `execute_case_00N`;
- trzy prawie identyczne output verifiers;
- trzy osobne backendy różniące się głównie komunikatami i kontraktem;
- case-specific public API jako trwała powierzchnia produktu;
- powtarzane konstrukcje raportu i obsługi błędów;
- możliwość dodania CASE-004 przez kopiowanie pliku.

### Twarda bramka konsolidacji

Konsolidacja może zostać zaakceptowana tylko wtedy, gdy:

1. CASE-001–003 nadal przechodzą jako realne runy;
2. wszystkie testy bezpieczeństwa nadal przechodzą;
3. nie powstaje ogólny system providerów ani adapterów;
4. liczba linii runtime wyraźnie spada;
5. worker nadal nie może zmieniać testów ani ogłaszać akceptacji;
6. nie pojawia się AI ani M3 w tym samym PR.

## Co następuje po konsolidacji

Dopiero po redukcji można podłączyć dokładnie jednego rzeczywistego workera AI do jednego z trzech istniejących przypadków.

Nie wolno jednocześnie:

- dodawać nowych przypadków benchmarku;
- budować multi-provider frameworka;
- rozwijać M3;
- przenosić projektu do realnego pilota wartości;
- uznawać `FIN-008` za zamknięte.

## Wpływ na FIN

| Ryzyko | Status | Uzasadnienie |
|---|---|---|
| `FIN-001` brak ostrego MVP | `PARTIAL` | zakres techniczny jest ostry, ale nie ma jeszcze realnego workera |
| `FIN-002` brak domkniętego use case | `PARTIAL` | kontrolowany use case jest domknięty technicznie, nie produktowo |
| `FIN-003` architektura wyprzedza potrzeby | `OPEN` | stack eksperymentalny nadal jest zbyt duży i wymaga redukcji |
| `FIN-004` zbyt wczesne abstrahowanie | `PARTIAL` | uniknięto platformy, a trzy runy dały dowód dla małego rdzenia |
| `FIN-005` platforma zamiast rozwiązania | `PARTIAL` | pilot jest wąski, ale nie został jeszcze skonsolidowany do rozwiązania |
| `FIN-006` roadmapa bez końca | `PARTIAL` | wykonano bramkę STOP po trzech przypadkach |
| `FIN-007` rozproszenie kierunków | `PARTIAL` | CASE-001–003 ukończono bez AI i M3 |
| `FIN-008` brak dowodów użycia | `OPEN` | techniczny benchmark nie jest realnym użyciem produktu |

Żadne ryzyko nie otrzymuje statusu `ELIMINATED`.
