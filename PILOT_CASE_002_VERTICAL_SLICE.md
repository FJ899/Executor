# CASE-002 Vertical Slice

## Status

```text
STATUS: IMPLEMENTED IN STACKED DRAFT
CASE-002 TECHNICAL GATE: PASSED
HUMAN ACCEPTANCE: PENDING
BASE PR: #23 CASE-001
AI WORKER: NOT USED
M3: NOT USED
AUTO MERGE: FORBIDDEN
```

Ten etap sprawdza drugi przypięty przypadek techniczny bez budowania uniwersalnego systemu adapterów.

## Przypięte wejście

```text
repository: litrgratis-pixel/executor-pilot-target
branch: case-002-broken
input commit: c3683bf37ad6a3f1d49c0ca05ebdd41627e9a5be
pilot contract blob: 0ae70e9f9a79e5e815f3d566ca5784059f461a9e
allowed path: project_registry/registry.py
observed failing property: CLOSED -> ACTIVE without reopen_reason
```

## Przepływ

```text
verified local checkout at pinned CASE-002 commit
→ separate Git worktree and result branch
→ deterministic restoration of the missing transition guard
→ exactly one allowed changed path
→ one result commit directly on pinned input
→ compileall in Docker
→ all 13 target tests in Docker
→ change.patch + report.json
→ ACTION_COMPLETED_REVIEW_REQUIRED
```

## Dowód wykonania

```text
Executor head: 1b0a90be3b3b36d918bb295a302556ee8ddbf63e
workflow: Verify Executor foundations
run: 30760104338
foundation-tests: SUCCESS
sandbox-security: SUCCESS
CASE-001 regression run: SUCCESS
CASE-002 pinned checkout: SUCCESS
CASE-002 real Docker run: SUCCESS
container cleanup: VERIFIED
```

Rzeczywisty run użył dokładnego commita `c3683bf37ad6a3f1d49c0ca05ebdd41627e9a5be`, utworzył jeden commit potomny, zmienił wyłącznie `project_registry/registry.py`, wykonał `compileall` oraz wszystkie 13 testów targetu w read-only Dockerze.

## Uruchomienie

```bash
creative-os-executor-pilot \
  --case 002 \
  --repository-root /path/to/case-002-checkout \
  --runs-root /path/outside/repository/pilot-runs \
  --executor-root . \
  --executor-commit "$(git rev-parse HEAD)" \
  --image sha256:<64-hex-image-id>
```

## Reguła naprawy

Worker może wyłącznie przywrócić warunek:

```python
if (
    project.status is ProjectStatus.CLOSED
    and target is ProjectStatus.ACTIVE
    and not reason
):
    raise InvalidTransitionError(
        "CLOSED -> ACTIVE requires a non-empty reopen_reason"
    )
```

Nie może dodawać nowych stanów, zmieniać testów ani rozszerzać modelu projektu.

## Ochrona przed fałszywym zaliczeniem

Run blokuje:

- inne repozytorium, commit lub blob kontraktu;
- brudny checkout źródłowy;
- katalog wyników wewnątrz źródła;
- brak dokładnie jednego przypiętego defektu;
- dodatkowy zmieniony plik;
- więcej niż jeden commit wynikowy albo zły parent;
- context CASE-001 użyty dla CASE-002;
- globalne external execution, auto-merge, sieć albo sekrety;
- nieudane testy, timeout lub niepotwierdzony cleanup.

## Znalezisko adversarial review

Pierwszy zielony realny run testował funkcję `execute_case_002`, ale nie sprawdzał nowej publicznej ścieżki `creative-os-executor-pilot --case 002`.

Dodano osobny test dispatchu CLI, który potwierdza:

- wybór wyłącznie pipeline CASE-002;
- użycie kontraktu CASE-002;
- brak wywołania CASE-001;
- poprawny kod wyjścia i raport JSON.

Ostateczny workflow `30760104338` przeszedł już z tym testem.

## Świadoma duplikacja

`executor/pilot_case_002.py` powtarza część mechanicznego przepływu CASE-001 i importuje jego wąskie helpery Git. Jest to zamierzone.

Nie wyodrębniamy jeszcze wspólnego frameworka. Po CASE-003 porównamy trzy rzeczywiste przebiegi i dopiero wtedy zdecydujemy:

- które mechanizmy są faktycznie wspólne;
- które są tylko szczegółami benchmarku;
- co usunąć zamiast utrwalać jako API.

## Czego etap nie udowadnia

- działania workera AI;
- wartości biznesowej;
- uniwersalnego wykonania zewnętrznych repozytoriów;
- potrzeby M3;
- terminalnego PASS;
- zamknięcia `FIN-008`.

## Następna bramka

CASE-002 ma zaliczoną bramkę techniczną, ale PR pozostaje draftem i nie jest autoryzowany do merge. Następny etap może dotyczyć wyłącznie CASE-003 na przypiętym commicie `c42bead2bbbff9c84486f17637ec80f35eeffa25`, nadal bez AI, M3 i uniwersalnego adaptera.
