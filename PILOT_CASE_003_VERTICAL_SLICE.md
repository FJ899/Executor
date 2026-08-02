# CASE-003 Vertical Slice

## Status

```text
STATUS: IMPLEMENTED IN STACKED DRAFT
REAL DOCKER RUN: PENDING
BASE PR: #24 CASE-002
AI WORKER: NOT USED
M3: NOT USED
AUTO MERGE: FORBIDDEN
```

CASE-003 jest trzecim i ostatnim kontrolowanym przypadkiem technicznym. Po jego wykonaniu nie wolno automatycznie dodawać kolejnego przypadku ani uogólniać runtime. Następną czynnością musi być porównanie CASE-001–003 i decyzja, co usunąć.

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

## Uruchomienie

```bash
creative-os-executor-pilot \
  --case 003 \
  --repository-root /path/to/case-003-checkout \
  --runs-root /path/outside/repository/pilot-runs \
  --executor-root . \
  --executor-commit "$(git rev-parse HEAD)" \
  --image sha256:<64-hex-image-id>
```

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
- nieudane testy, timeout lub niepotwierdzony cleanup.

## Bramka

CASE-003 może otrzymać `TECHNICAL GATE: PASSED` dopiero wtedy, gdy jeden workflow potwierdzi:

1. pełne foundation tests;
2. istniejące testy bezpieczeństwa sandboxu;
3. realny CASE-001;
4. realny CASE-002;
5. realny CASE-003 na dokładnym przypiętym commicie;
6. pełne 13 testów każdego targetu;
7. cleanup wszystkich kontenerów.

## Po CASE-003

Następny etap nie jest CASE-004.

Wymagane jest porównanie:

- powtórzonego kodu między trzema przypadkami;
- czasu i liczby zmian potrzebnych do dodania przypadku;
- mechanizmów faktycznie wspólnych;
- elementów benchmarkowych do usunięcia;
- tego, czy dalsze inwestowanie w deterministyczny pilot ma sens przed realnym workerem AI.

## Czego etap nie udowadnia

- wartości biznesowej Executora;
- działania workera AI;
- przewagi nad zwykłym coding agentem;
- potrzeby M3;
- terminalnego PASS;
- zamknięcia `FIN-008`.
