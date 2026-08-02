# CASE-003 Vertical Slice

## Status

```text
STATUS: IMPLEMENTED IN STACKED DRAFT
TECHNICAL GATE: PASSED
HUMAN ACCEPTANCE: PENDING
BASE PR: #24 CASE-002
AI WORKER: NOT USED
M3: NOT USED
AUTO MERGE: FORBIDDEN
```

CASE-003 jest trzecim i ostatnim kontrolowanym przypadkiem technicznym. Po jego wykonaniu nie wolno automatycznie dodawać kolejnego przypadku ani uogólniać runtime bez porównania CASE-001–003.

## Przypięte wejście

```text
repository: litrgratis-pixel/executor-pilot-target
branch: case-003-broken
input commit: c42bead2bbbff9c84486f17637ec80f35eeffa25
pilot contract blob: 0ae70e9f9a79e5e815f3d566ca5784059f461a9e
allowed path: project_registry/registry.py
observed failing property: output order depends on input order
```

Dwie obserwowane porażki dotyczą jednej własności:

```text
test_different_input_order_produces_identical_stdout
test_json_output_is_sorted_stable_and_utf8_friendly
```

## Przepływ

```text
verified local checkout at pinned CASE-003 commit
→ separate Git worktree and result branch
→ deterministic replacement of one known to_payload defect
→ exactly one allowed changed path
→ one result commit directly on pinned input
→ compileall in Docker
→ all 13 target tests in Docker
→ change.patch + report.json
→ ACTION_COMPLETED_REVIEW_REQUIRED
```

## Reguła naprawy

Worker może wyłącznie zastąpić iterację po kolejności słownika:

```python
[project.to_mapping() for project in self._projects.values()]
```

kanoniczną kolejnością:

```python
[
    self._projects[project_id].to_mapping()
    for project_id in sorted(self._projects)
]
```

Nie zmienia `json.dumps`, obsługi UTF-8, końcowego znaku nowej linii ani CLI targetu.

## Dowód wykonania

Ostateczny head:

```text
3490d474dcc983e5104b9ca4cf56432486196756
```

GitHub Actions:

```text
workflow: Verify Executor foundations
run: 30764964269
conclusion: success
```

Jeden workflow potwierdził:

- pełne foundation tests;
- 10/10 istniejących testów bezpieczeństwa sandboxu;
- realny CASE-001;
- realny CASE-002;
- realny CASE-003 na dokładnym przypiętym commicie;
- `compileall` i pełne 13 testów każdego targetu;
- brak zmian w trzech źródłowych checkoutach po wykonaniu;
- cleanup kontenerów testowych oraz CASE-001–003.

## Adversarial review

Pierwszy zielony run potwierdzał trzy naprawy i cleanup, ale nie sprawdzał bezpośrednio po wykonaniu, czy źródłowe checkouty nadal wskazują przypięte commity i są czyste.

Dodano więc obowiązkową bramkę CI:

```text
Verify source checkouts remain pinned and clean
```

Dla każdego przypadku sprawdzany jest dokładny `HEAD` oraz pusty `git status --porcelain --untracked-files=all`.

## Ochrona przed fałszywym zaliczeniem

Run blokuje:

- inne repozytorium, commit lub blob kontraktu;
- brudny checkout źródłowy;
- katalog wyników wewnątrz źródła;
- brak dokładnie jednego przypiętego defektu;
- dodatkowy zmieniony plik;
- więcej niż jeden commit wynikowy albo zły parent;
- context CASE-001 lub CASE-002 użyty dla CASE-003;
- globalne external execution, auto-merge, sieć albo sekrety;
- nieudane testy, timeout lub niepotwierdzony cleanup;
- zmianę albo przesunięcie źródłowego checkoutu.

## Koszt trzeciego przypadku

Różnica względem CASE-002 obejmuje:

```text
7 plików
353 linie case-specific runtime
168 linii testów jednostkowych
88 linii realnego testu integracyjnego
70 linii rozszerzenia testów CLI
16 linii CI
124 linie dokumentacji
```

To jest dowód, że obecna forma nie skaluje się przez kopiowanie kolejnych przypadków.

## Po CASE-003

Następny etap nie jest CASE-004.

Wymagane jest porównanie:

- powtórzonego kodu między trzema przypadkami;
- mechanizmów faktycznie wspólnych;
- elementów benchmarkowych do usunięcia;
- najmniejszego rdzenia potrzebnego przed realnym workerem AI;
- tego, czy dalsze inwestowanie w deterministyczny pilot ma sens.

## Czego etap nie udowadnia

- wartości biznesowej Executora;
- działania workera AI;
- przewagi nad zwykłym coding agentem;
- potrzeby M3;
- terminalnego PASS;
- zamknięcia `FIN-008`.
