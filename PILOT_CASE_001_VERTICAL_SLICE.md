# CASE-001 Vertical Slice

## Status

```text
STATUS: TECHNICALLY VERIFIED IN DRAFT
REAL PINNED DOCKER RUN: VERIFIED
ADVERSARIAL REVIEW: COMPLETED
AI WORKER: NOT USED
M3: NOT USED
AUTO MERGE: FORBIDDEN
HUMAN ACCEPTANCE: PENDING
```

Ten etap sprawdza wyłącznie, czy Executor potrafi domknąć jeden przypięty przypadek techniczny od czystego wejścia do wyniku wymagającego przeglądu człowieka.

## Przypięte wejście

```text
repository: litrgratis-pixel/executor-pilot-target
branch: case-001-broken
input commit: 3934a94a5eebf750079200589d6dc40e024d44a0
pilot contract blob: 0ae70e9f9a79e5e815f3d566ca5784059f461a9e
allowed path: project_registry/registry.py
```

## Zweryfikowany przepływ

```text
verified local checkout at the pinned input commit
→ separate Git worktree and local result branch
→ deterministic replacement of the one known defect
→ exactly one allowed changed path
→ one result commit directly on the pinned input
→ compileall in Docker
→ all 13 target tests in Docker
→ change.patch + report.json
→ verified container cleanup
→ ACTION_COMPLETED_REVIEW_REQUIRED
```

## Dowód CI

```text
workflow: Verify Executor foundations
successful run: 30759542282
foundation-tests: SUCCESS
sandbox-security: SUCCESS
existing Docker sandbox tests: 10/10 OK
real pinned CASE-001 integration: OK
container cleanup: VERIFIED
```

Wcześniejszy run `30759264604` zakończył się kontrolowanym `TESTS_FAILED`, ponieważ testy były uruchamiane z `/workspace`, a katalog `/source/tests` nie był importowalny. Naprawa nie poluzowała sandboxu: pilot uruchamia komendy z read-only `/source`, a cache bajtkodu kieruje do `/workspace/pycache`.

## Znaleziska z adversarial review

### 1. Git worktree metadata

`verify_source_tree` traktował plik `.git` używany przez linked worktree jako dodatkowy plik źródłowy. Weryfikator ignoruje teraz wyłącznie główny wpis metadanych `.git`; wszystkie inne dodatkowe pliki nadal blokują wykonanie.

### 2. Read-only source i cache Pythona

`compileall` potrzebuje miejsca na cache. Pilot ustawia `PYTHONPYCACHEPREFIX=/workspace/pycache`, więc źródło pozostaje read-only i zgodne z commitem wynikowym.

### 3. Kod wykonywany przez hooki Git na hoście

`git worktree add`, `git switch` i `git commit` mogły uruchomić lokalne hooki poza sandboxem. Wszystkie wywołania Git używane przez pilot:

- usuwają odziedziczone zmienne `GIT_*`;
- wyłączają systemową konfigurację Git;
- ustawiają `core.hooksPath=/dev/null`;
- wyłączają fsmonitor i podpisywanie commitów;
- wyłączają globalny plik atrybutów i automatyczne CRLF;
- generują diff bez external diff i textconv.

Test regresyjny tworzy faktycznie wykonywalny `post-checkout` hook i potwierdza, że nie może on uruchomić się na hoście.

### 4. Blokada nie może sama zabrudzić repo

Odrzucony `runs_root` wewnątrz checkoutu nie tworzy już raportu ani katalogu w blokowanym repo. Test potwierdza brak zmiany stanu źródła.

## Uruchomienie

Wymagane są:

- lokalny checkout repo targetu dokładnie na przypiętym commicie;
- lokalny checkout Executora na commicie zawierającym tę implementację;
- Docker;
- lokalny, niezmienny obraz wskazany jako `sha256:<64 hex>`;
- katalog wyników poza checkoutem targetu.

```bash
creative-os-executor-pilot \
  --repository-root /path/to/executor-pilot-target \
  --runs-root /path/outside/repository/pilot-runs \
  --executor-root . \
  --executor-commit "$(git rev-parse HEAD)" \
  --image sha256:<64-hex-image-id>
```

## Wynik

Każdy udany run zapisuje:

- `report.json`;
- `change.patch`;
- branch i worktree wyniku;
- commit wejściowy i wynikowy;
- dokładne komendy;
- stdout, stderr, exit code, timeout i dowód cleanupu kontenera;
- status wymagający decyzji człowieka.

## Ochrona przed fałszywym zaliczeniem

Run jest blokowany, gdy:

- checkout nie wskazuje dokładnie przypiętego repo i commita;
- `PILOT_CONTRACT.md` ma inny blob;
- źródłowy checkout jest brudny;
- katalog wyników znajduje się wewnątrz repo źródłowego;
- worker nie znajduje dokładnie jednej znanej regresji;
- zmieniono cokolwiek poza `project_registry/registry.py`;
- commit wynikowy nie jest pojedynczym bezpośrednim potomkiem wejścia;
- globalne wykonywanie projektów zewnętrznych zostało włączone;
- auto-merge, sieć albo domyślne sekrety są włączone;
- sandbox otrzymuje inne repo, purpose, source albo commit;
- testy lub cleanup kontenera nie kończą się poprawnie;
- lokalna konfiguracja Git próbuje uruchomić hook, fsmonitor, external diff albo textconv.

## Pozostałe ograniczenia

- Executor nie pobiera repozytorium; otrzymuje wcześniej przygotowany lokalny checkout.
- Branch wynikowy nie jest wypychany do GitHub i nie powstaje PR targetu.
- Dowód CI potwierdza powstanie raportu i patcha, ale nie zachowuje ich jako trwałego artefaktu workflow.
- Worker jest świadomie zakodowany wyłącznie dla jednej znanej regresji.
- CASE-002 i CASE-003 nie są zaimplementowane.

## Elementy tymczasowe do usunięcia lub zastąpienia

Po ukończeniu trzech przypadków technicznych nie wolno utrwalać jako platformy:

- tekstowych stałych `_BROKEN_ADD_MANY` i `_FIXED_ADD_MANY`;
- komendy `creative-os-executor-pilot`;
- klasy `PilotCase001DockerSandboxBackend`;
- kontraktu `PilotCase001Contract` w obecnej postaci;
- case-specific statusu i dokumentu jako publicznego API.

Dopiero porównanie CASE-001–003 może wskazać najmniejszy wspólny mechanizm. Nie tworzymy go wcześniej.

## Czego ten etap nie udowadnia

Nie jest to:

- uniwersalny `execute-task`;
- worker AI;
- dowód wartości biznesowej;
- zamknięcie `FIN-008`;
- zgoda na wykonanie innych repozytoriów;
- terminalny `PASS`;
- uzasadnienie dla M3.

## Bramka

```text
CASE-001 TECHNICAL GATE: PASSED
PR MERGE: NOT AUTHORIZED
NEXT TECHNICAL CASE: CASE-002
NEXT PRODUCT EVIDENCE: STILL NOT STARTED
```

Kod pozostaje w draft PR do decyzji człowieka. Zaliczenie tej bramki pozwala przygotować CASE-002 tym samym rygorem, ale nie pozwala jeszcze uogólniać architektury ani podłączać workera AI.
