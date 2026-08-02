# CASE-002 Vertical Slice

## Status

```text
STATUS: IMPLEMENTED IN STACKED DRAFT
REAL DOCKER RUN: PENDING
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

## Bramka

CASE-002 może otrzymać `TECHNICAL GATE: PASSED` dopiero po rzeczywistym runie CI na dokładnym commicie wejściowym, pełnych 13 testach w Dockerze i potwierdzonym cleanupie. PR pozostaje draftem i nie jest autoryzowany do merge.
