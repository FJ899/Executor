# Executor MVP Progress 001 — CASE-001

## Status

```text
DATE: 2026-08-02
PROJECT 0 — PILOT TARGET: COMPLETED
PROJECT 1 — CASE-001 VERTICAL SLICE: TECHNICALLY PASSED IN DRAFT
PRODUCT VALUE VALIDATION: NOT STARTED
FIN-008: OPEN
M3: FROZEN OUTSIDE CRITICAL PATH
```

Ten dokument aktualizuje bazowy plan naprawczy po pierwszym rzeczywistym pionowym przebiegu. Nie zastępuje `EXECUTOR_MVP_REMEDIATION_AND_VALIDATION_PLAN_v1.0.md` ani nie oznacza ukończenia Executor 1.0.

## Domknięty poligon

```text
repository: litrgratis-pixel/executor-pilot-target
baseline PR: #1
baseline merge: dc094679ef3e2d5cf5f1aa0ff0fd54d16f201154
baseline tests: 13/13 OK
benchmark branches: case-001-broken, case-002-broken, case-003-broken
```

Zielona baza została świadomie scalona. Trzy czerwone gałęzie pozostały niezmiennymi wejściami i nie zostały scalone.

## CASE-001

```text
Executor draft PR: #23
input commit: 3934a94a5eebf750079200589d6dc40e024d44a0
allowed target path: project_registry/registry.py
final verified Executor head: cc1db2e75ce9a46932e3bcd2303aa4a9976ec5a9
final workflow run: 30759590855
status: ACTION_COMPLETED_REVIEW_REQUIRED
```

Zweryfikowany przebieg:

```text
pinned checkout
→ separate worktree and local branch
→ deterministic repair
→ exactly one changed path
→ one direct result commit
→ compileall in read-only Docker source
→ all 13 target tests in Docker
→ diff and report
→ verified container cleanup
```

## Porażki, które dostarczyły wiedzy

### P-001 — linked worktree wyglądał jak zmienione źródło

Główny plik metadanych `.git` w linked worktree był uznawany za dodatkowy plik. Weryfikator ignoruje teraz wyłącznie ten jeden wpis, nie pozostałe dodatkowe pliki.

### P-002 — testy nie startowały z właściwego katalogu

Pierwszy realny run `30759264604` zakończył się `TESTS_FAILED`, ponieważ workdir pozostał `/workspace`. Poprawka uruchamia komendy z read-only `/source`, a cache bajtkodu kieruje do `/workspace/pycache`.

### P-003 — Git mógł wykonać kod poza sandboxem

Adversarial review wykazał, że `worktree add`, `switch` i `commit` mogły uruchomić lokalne hooki Git. Pilot usuwa odziedziczone `GIT_*`, wyłącza hooki, fsmonitor, systemową konfigurację, globalne attributes, podpisywanie oraz zewnętrzny diff/textconv. Test z wykonywalnym `post-checkout` hookiem potwierdza brak wykonania na hoście.

### P-004 — blokada mogła zabrudzić blokowane repo

Nieprawidłowy `runs_root` wewnątrz checkoutu mógł wcześniej prowadzić do utworzenia raportu w źródle. Teraz blokada następuje bez jakiejkolwiek delty w repo.

## Ocena bramki Projektu 1

| Kryterium | CASE-001 |
|---|---|
| przypięte repo i commit | `PASS` |
| osobny worktree i branch | `PASS` |
| zmiana tylko dozwolonego pliku | `PASS` |
| pojedynczy commit wynikowy | `PASS` |
| compileall w sandboxie | `PASS` |
| pełne testy targetu w sandboxie | `PASS` |
| diff i report | `PASS` |
| brak auto-merge | `PASS` |
| decyzja pozostawiona człowiekowi | `PASS` |
| worker AI | `NOT IN SCOPE` |
| wartość biznesowa | `NOT TESTED` |

Werdykt techniczny: `CONTINUE TO CASE-002`.

Werdykt produktowy: `NO CLAIM`.

## Aktualizacja ryzyk FIN

| Ryzyko | Status | Aktualny dowód |
|---|---|---|
| `FIN-001` brak ostrego MVP | `PARTIAL` | istnieje zamknięty techniczny use case i wynik, ale nie pełne 1.0 |
| `FIN-002` brak domkniętego use case | `PARTIAL` | CASE-001 jest domknięty technicznie; wymagane są jeszcze CASE-002 i CASE-003 |
| `FIN-003` architektura wyprzedza potrzeby | `PARTIAL` | praca dotyczyła wyłącznie przeszkód ujawnionych przez realny run |
| `FIN-004` zbyt wczesne abstrahowanie | `PARTIAL` | nie powstał wspólny framework; kod pozostaje jawnie case-specific |
| `FIN-005` platforma zamiast rozwiązania | `PARTIAL` | dostarczono jeden wynik, ale istniejąca szeroka infrastruktura nadal pozostaje |
| `FIN-006` roadmapa bez końca | `PARTIAL` | użyto konkretnej bramki i zapisano wynik `CONTINUE` |
| `FIN-007` rozproszenie kierunków | `PARTIAL` | M3 i AI pozostają poza aktywnym zakresem |
| `FIN-008` brak dowodów użycia | `OPEN` | techniczny poligon nie jest realnym użyciem produktu |

Żadne ryzyko nie otrzymuje statusu `ELIMINATED`.

## Dług techniczny świadomie tymczasowy

Po CASE-003 należy usunąć lub zastąpić:

- `_BROKEN_ADD_MANY` i `_FIXED_ADD_MANY`;
- `PilotCase001Contract`;
- `PilotCase001DockerSandboxBackend`;
- `creative-os-executor-pilot`;
- case-specific publiczne statusy i dokumenty.

Nie wolno tworzyć wspólnej abstrakcji przed porównaniem trzech rzeczywistych przypadków technicznych.

## Następny etap

```text
CASE-002 only
→ pinned c3683bf37ad6a3f1d49c0ca05ebdd41627e9a5be
→ same external checkout and sandbox boundaries
→ deterministic worker for CLOSED -> ACTIVE rule
→ no AI
→ no M3
→ no universal adapter
```

PR #23 pozostaje draftem i nie jest autoryzowany do merge. CASE-002 powinien powstać jako kolejny mały, odwracalny eksperyment albo jako rozszerzenie tego samego draftu dopiero po decyzji seniora, która opcja daje mniejszy koszt porównania i późniejszego usunięcia kodu.
