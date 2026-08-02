# Executor MVP Progress 002 — CASE-002

## Status

```text
PROJECT 1 / CASE-002 TECHNICAL GATE: PASSED
HUMAN ACCEPTANCE: PENDING
EXECUTOR PR: #24 STACKED DRAFT
BASE PR: #23 CASE-001
AI WORKER: NOT USED
M3: NOT USED
PRODUCT VALUE VALIDATION: NOT STARTED
```

## Cel etapu

Sprawdzić, czy pionowy przepływ przygotowany dla CASE-001 potrafi domknąć drugi, semantycznie inny błąd bez:

- zmiany testów;
- rozszerzenia do uniwersalnego adaptera;
- podłączenia modelu AI;
- odblokowania globalnego wykonywania projektów zewnętrznych;
- użycia M3 lub terminalnego PASS.

## Przypięte wejście

```text
repository: litrgratis-pixel/executor-pilot-target
issue: #3
branch: case-002-broken
input commit: c3683bf37ad6a3f1d49c0ca05ebdd41627e9a5be
contract blob: 0ae70e9f9a79e5e815f3d566ca5784059f461a9e
allowed path: project_registry/registry.py
```

Obserwowana porażka przed naprawą:

```text
FAIL: test_closed_project_requires_reason_before_reopening
Ran 13 tests
FAILED (failures=1)
```

## Wykonany przepływ

```text
verified pinned checkout
→ isolated worktree and result branch
→ deterministic restoration of CLOSED -> ACTIVE guard
→ exactly one allowed path changed
→ one direct child result commit
→ compileall in read-only Docker source
→ all 13 target tests in Docker
→ change.patch + report.json
→ verified container cleanup
→ ACTION_COMPLETED_REVIEW_REQUIRED
```

## Dowód

```text
Executor PR: #24
verified head before evidence-only documentation update:
1b0a90be3b3b36d918bb295a302556ee8ddbf63e
workflow: Verify Executor foundations
run_id: 30760104338
foundation-tests: SUCCESS
sandbox-security: SUCCESS
CASE-001 regression run: SUCCESS
CASE-002 real Docker run: SUCCESS
cleanup: VERIFIED
```

## Zakres naprawy

Worker przywrócił wyłącznie warunek wymagający niepustego `reopen_reason` dla przejścia:

```text
CLOSED -> ACTIVE
```

Nie zmieniono:

- modelu statusów;
- testów targetu;
- kontraktu pilota;
- CI targetu;
- innych plików źródłowych.

## Znalezisko adversarial review

Pierwszy zielony przebieg udowadniał funkcję wykonawczą, ale nie nowe rozgałęzienie publicznej komendy:

```text
creative-os-executor-pilot --case 002
```

Dodano test dispatchu CLI potwierdzający:

- wywołanie wyłącznie CASE-002;
- użycie kontraktu CASE-002;
- brak wywołania CASE-001;
- poprawny raport i kod wyjścia.

Ostateczny workflow przeszedł z tym testem.

## Świadoma duplikacja

CASE-002 nie został użyty jako pretekst do utworzenia frameworka adapterów. Moduł case-specific powtarza część mechaniki i korzysta z wąskich helperów Git CASE-001.

Decyzja o ekstrakcji jest odroczona do zakończenia CASE-003. Wtedy istnieją trzy konkretne przebiegi pozwalające odróżnić:

- rzeczywiste elementy wspólne;
- szczegóły pojedynczych usterek;
- kod, który należy usunąć po benchmarku.

## Wpływ na FIN

| Ryzyko | Status po CASE-002 | Uzasadnienie |
|---|---|---|
| `FIN-001` brak ostrego MVP | `PARTIAL` | istnieje zamknięty typ technicznego zadania, ale brak realnego pilota wartości |
| `FIN-002` brak domkniętego use case | `PARTIAL` | dwa z trzech kontrolowanych przypadków są technicznie domknięte |
| `FIN-003` architektura wyprzedza potrzeby | `OPEN` | istniejące rozbudowane warstwy nie zostały jeszcze usunięte |
| `FIN-004` zbyt wczesne abstrahowanie | `PARTIAL` | nie utworzono nowego frameworka, ale case-specific runtime nadal jest rozbudowany |
| `FIN-005` platforma zamiast rozwiązania | `PARTIAL` | aktywny zakres pozostaje jednym benchmarkiem, lecz produkt nie został jeszcze zredukowany |
| `FIN-006` roadmapa bez końca | `PARTIAL` | zastosowano następną bramkę, ale decyzja STOP/RELEASE jeszcze nie zapadła |
| `FIN-007` rozproszenie kierunków | `PARTIAL` | kontynuowano wyłącznie CASE-002; M3 i AI pozostały zamrożone |
| `FIN-008` brak dowodów użycia | `OPEN` | benchmark techniczny nie jest realnym użyciem produktu |

Żadne ryzyko nie otrzymuje statusu `ELIMINATED`.

## Następna bramka

```text
CASE-003 only
→ pinned commit c42bead2bbbff9c84486f17637ec80f35eeffa25
→ deterministic canonical ordering repair
→ same worktree and sandbox boundaries
→ CASE-001 and CASE-002 regression runs remain green
→ no AI
→ no M3
→ no universal adapter before evidence from all three cases
```
