# CASE-001 Vertical Slice

## Status

```text
STATUS: IMPLEMENTED IN DRAFT
REAL DOCKER RUN: PENDING
AI WORKER: NOT USED
M3: NOT USED
AUTO MERGE: FORBIDDEN
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

## Przepływ

```text
verified local checkout at the pinned input commit
→ separate Git worktree and local result branch
→ deterministic replacement of the one known defect
→ exactly one allowed changed path
→ one result commit directly on the pinned input
→ compileall in Docker
→ full unittest suite in Docker
→ change.patch + report.json
→ ACTION_COMPLETED_REVIEW_REQUIRED
```

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

Każdy run zapisuje:

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
- testy lub cleanup kontenera nie kończą się poprawnie.

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

Kod może przejść do następnego etapu dopiero po rzeczywistym opt-in teście Docker na przypiętym target repo. Sam test jednostkowy z fake backendem nie jest dowodem pełnego pionowego przepływu.
