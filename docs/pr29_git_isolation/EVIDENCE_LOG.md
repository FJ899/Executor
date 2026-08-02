# PR #29 — dziennik dowodów

Każdy wpis dotyczy dokładnie jednego SHA i jednej próby. Nie wolno przenosić wyniku między SHA.

## Wymagany łańcuch

```text
VULNERABLE_IMPLEMENTATION_SHA
→ TEST_ONLY_SHA
→ RED_RUN_ID
→ FIXED_IMPLEMENTATION_SHA
→ GREEN_RUN_ID
```

## EVIDENCE-PR29-BASELINE-001

```text
PR: #29
VULNERABLE_IMPLEMENTATION_SHA: 514ba20d67bd415e438440c62f47307709177a7f
BASELINE_WORKFLOW: 30766241419
BASELINE_FOUNDATION_TESTS: SUCCESS
BASELINE_SANDBOX_SECURITY: SUCCESS
BASELINE_CASE_001: SUCCESS
BASELINE_CASE_002: SUCCESS
BASELINE_CASE_003: SUCCESS

DECISION: REWORK
READY: NO
MERGE: NO
```

### Środowisko reprodukcji

```text
git version: 2.47.3
reproducer: evidence/reproduce_git_filter_escape.sh
output: evidence/reproduction_output.txt
verification report: evidence/EXECUTOR_PR29_VERIFICATION.md
```

### Obserwacja

- `.git/info/attributes` przypisał filtr do dozwolonego pliku;
- `.git/config` zdefiniował lokalne programy `clean` i `smudge`;
- marker potwierdził wykonanie obu faz;
- working tree pozostał czysty;
- source i worktree wskazywały ten sam commit.

### Ograniczenie dowodu

Bazowa reprodukcja nie przypisuje każdego wykonania do pojedynczego polecenia Git. To ograniczenie zostało później zaadresowane w diagnostyce per polecenie.

### Wniosek

```text
HOST GIT FILTER ISOLATION: FAILED
CURRENT CI: GREEN BUT INSUFFICIENT
FALSE SUCCESS WITHIN TESTED VECTOR: POSSIBLE
```

## EVIDENCE-PR29-RED-002

```text
DOCUMENTATION_SHA: 9b71726eadd152984bd906bde2d8f0f8cd96dc39
TEST_ONLY_SHA: ea3226dc2836d6287af7a080d12d3adeb7787298
RED_RUN_ID: 30767747711
FIXED_IMPLEMENTATION_SHA: PENDING
GREEN_RUN_ID: PENDING

WORKFLOW_CONCLUSION: FAILURE
FOUNDATION_TESTS: FAILURE AS EXPECTED
SANDBOX_SECURITY: SUCCESS
REAL_CASE_001: SUCCESS
REAL_CASE_002: SUCCESS
REAL_CASE_003: SUCCESS
SOURCE_CHECKOUTS_PINNED_AND_CLEAN: SUCCESS
CONTAINER_CLEANUP: SUCCESS
```

### Czerwone testy

Na Git `2.54.0` zawiodło dokładnie sześć nowych testów bezpieczeństwa:

1. Executor uruchamia Git przeciwko wejściowemu checkoutowi lub `.git`;
2. `includeIf` ładuje wykonywalną konfigurację filtra;
3. `include.path` ładuje wykonywalną konfigurację filtra;
4. lokalny filtr `clean` wykonuje się na hoście;
5. lokalny filtr `process` startuje na hoście;
6. lokalny filtr `smudge` wykonuje się na hoście.

Istniejący test `post-checkout` pozostał zielony. Oznacza to, że nowe testy nie obalają wcześniejszej ochrony hooków, lecz wykrywają dodatkowe niepokryte kanały.

### Ślad bezpośrednich wywołań Git

Test trace wykazał sześć wywołań skierowanych do wejściowego checkoutu:

```text
git remote get-url origin
git cat-file -e <commit>^{commit}
git rev-parse HEAD
git rev-parse <commit>:PILOT_CONTRACT.md
git status --porcelain --untracked-files=all
git worktree add --detach ... <commit>
```

### Diagnostyka per polecenie — Git 2.47.3

Pliki:

```text
evidence/diagnose_git_filter_surface.py
evidence/git_filter_surface_output.csv
```

Potwierdzone wykonania:

```text
clean: status, diff, add, commit
smudge: worktree add
process: status, worktree add, diff, add
```

`rev-parse`, `remote`, `cat-file` i `ls-tree` nie uruchomiły testowanych filtrów w tej konkretnej wersji i konfiguracji. To wynik diagnostyczny, nie podstawa do osłabienia niezmiennika „żaden Git na wejściowym .git”.

### Wniosek czerwonego etapu

```text
RED TESTS: VALID
SYNTAX / FIXTURE FAILURE: NO
VULNERABLE IMPLEMENTATION DETECTED: YES
FUNCTIONAL CASES STILL WORK: YES
IMPLEMENTATION FIX: NOT STARTED
```

## Szablon kolejnego wpisu

```text
EVIDENCE ID:
HEAD SHA:
BASELINE SHA:
TEST-ONLY SHA:
FIXED SHA:
WORKFLOW / RUN ID:
DATE AND ENVIRONMENT:
GIT VERSION:
INPUT MODEL:
ADR:
COMMAND:
PROCESS CWD:
SANITIZED ENVIRONMENT:
EXIT CODE:
STDOUT:
STDERR:
CHILD PROCESSES:
MARKERS:
INPUT MANIFEST BEFORE:
INPUT MANIFEST AFTER:
OBJECT IDENTITY:
ORIGIN ANCHOR:
CASE-001:
CASE-002:
CASE-003:
CLEANUP:
CONCLUSION:
```
