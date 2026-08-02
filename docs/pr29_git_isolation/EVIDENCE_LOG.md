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
TEST_ONLY_SHA: PENDING
RED_RUN_ID: PENDING
FIXED_IMPLEMENTATION_SHA: PENDING
GREEN_RUN_ID: PENDING

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

Bazowa reprodukcja nie przypisuje jeszcze każdego wykonania do pojedynczego polecenia Git. Faza diagnostyczna musi izolować polecenia przez czyszczenie markera przed każdą próbą.

### Wniosek

```text
HOST GIT FILTER ISOLATION: FAILED
CURRENT CI: GREEN BUT INSUFFICIENT
FALSE SUCCESS WITHIN TESTED VECTOR: POSSIBLE
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
