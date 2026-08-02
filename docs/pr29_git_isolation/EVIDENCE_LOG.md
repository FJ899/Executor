# PR #29 — dziennik dowodów

Każdy wpis dotyczy dokładnie jednego SHA i jednej próby. Nie wolno przenosić wyniku między SHA.

## Wymagany łańcuch

```text
VULNERABLE_IMPLEMENTATION_SHA
→ TEST_ONLY_SHA
→ RED_RUN_ID
→ ADR_DECISION_SHA
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
GIT_BINARY_PATH: not recorded in original local reproduction
GIT_VERSION: 2.47.3
GIT_BUILD_OR_IMAGE_DIGEST: not applicable / host binary
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

Bazowa reprodukcja nie przypisuje każdego wykonania do pojedynczego polecenia Git. Ograniczenie zostało później zaadresowane w diagnostyce per polecenie.

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
EVIDENCE_RECORD_SHA: 75943321535b872a7cd242cd31e467a90df9d1cd
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

### Toolchain czerwonego runu

```text
GIT_BINARY_PATH: /usr/bin/git
GIT_VERSION: 2.54.0
GIT_BUILD_OR_IMAGE_DIGEST: GitHub-hosted runner image; immutable digest not recorded
```

### Czerwone testy

Na Git `2.54.0` zawiodło dokładnie sześć nowych testów bezpieczeństwa:

1. Executor uruchamia Git przeciwko wejściowemu checkoutowi lub `.git`;
2. `includeIf` ładuje wykonywalną konfigurację filtra;
3. `include.path` ładuje wykonywalną konfigurację filtra;
4. lokalny filtr `clean` wykonuje się na hoście;
5. lokalny filtr `process` startuje na hoście;
6. lokalny filtr `smudge` wykonuje się na hoście.

Istniejący test `post-checkout` pozostał zielony.

### Ślad bezpośrednich wywołań Git

```text
git remote get-url origin
git cat-file -e <commit>^{commit}
git rev-parse HEAD
git rev-parse <commit>:PILOT_CONTRACT.md
git status --porcelain --untracked-files=all
git worktree add --detach ... <commit>
```

### Diagnostyka per polecenie — Git 2.47.3

```text
clean: status, diff, add, commit
smudge: worktree add
process: status, worktree add, diff, add
```

`rev-parse`, `remote`, `cat-file` i `ls-tree` nie uruchomiły testowanych filtrów w tej konkretnej wersji i konfiguracji. To wynik diagnostyczny, nie podstawa do osłabienia invariantu.

### Wniosek czerwonego etapu

```text
RED TESTS: VALID
SYNTAX / FIXTURE FAILURE: NO
VULNERABLE IMPLEMENTATION DETECTED: YES
FUNCTIONAL CASES STILL WORK: YES
IMPLEMENTATION FIX: NOT STARTED
```

## EVIDENCE-PR29-ADR-003

```text
PRE-ADR HEAD: 75943321535b872a7cd242cd31e467a90df9d1cd
ADR_DECISION_SHA: recorded in PR #29 body after commit creation
ADR LOCATION: REWORK_PLAN.md / ADR-001
ADR STATUS: ACCEPTED FOR PR #29 IMPLEMENTATION
MVP INPUT MODEL: CONTROLLED_HTTPS_FETCH_V1
LOCAL CHECKOUT: UNSUPPORTED / FAIL-CLOSED
OFFLINE BUNDLE: DEFERRED
IMPLEMENTATION FIX: NOT STARTED
```

### Zakres v2

```text
BASELINE_SCOPE: 21 original runtime files
CURRENT REWORK ADDITIONS: 10 docs/evidence files plus named tests in existing test_pilot_git_isolation.py
FUTURE IMPLEMENTATION: exact path allowlist in GATE_CARD.md and REWORK_PLAN.md
UNAUTHORIZED_FILES: every other path
```

### ADR toolchain pin

```text
TOOL IMAGE: alpine/git@sha256:0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd
PLATFORM: linux/amd64
EXPECTED GIT_BINARY_PATH: /usr/bin/git
EXPECTED GIT_VERSION: 2.54.0
```

### Definicje dowodu

```text
INPUT MODEL COMPLIANCE:
Only the exact CONTROLLED_HTTPS_FETCH_V1 contract is accepted.

OBJECT IDENTITY:
Exact full commit, root tree and PILOT_CONTRACT.md blob are verified in the controlled repository.

ORIGIN ANCHOR:
The exact repository is fetched through controlled HTTPS from the allowlisted GitHub endpoint using the pinned toolchain.
```

`OBJECT IDENTITY` nie oznacza automatycznie pochodzenia. `ORIGIN ANCHOR` nie dowodzi autorstwa commita.

### Status powierzchni

```text
CLEAN/SMUDGE/PROCESS DIAGNOSTICS: COMPLETE FOR TESTED COMMANDS
GENERAL HOST GIT EXECUTION SURFACE: PARTIAL — REMAINING TESTS DERIVE FROM ADR-001
```

### Surowe evidence wymagane przed final review

```text
ARTIFACT_NAME: pr29-git-isolation-<full-head-sha>
RUN_ID: PENDING
HEAD_SHA: PENDING
ARCHIVE_SHA256: PENDING
RETENTION / DOWNLOAD LOCATION: PENDING
```

Brak artefaktu powoduje `DEFINED ADVERSARIAL SUITE: FAIL` i blokuje `ACCEPT`.

## Szablon kolejnego wpisu

```text
EVIDENCE ID:
HEAD SHA:
BASELINE SHA:
TEST-ONLY SHA:
ADR DECISION SHA:
FIXED SHA:
WORKFLOW / RUN ID:
DATE AND ENVIRONMENT:
INPUT MODEL:
ADR:
GIT_BINARY_PATH:
GIT_VERSION:
GIT_BUILD_OR_IMAGE_DIGEST:
PLATFORM:
CANONICAL SOURCE URL:
EXPECTED COMMIT:
FETCHED COMMIT:
ROOT TREE:
CONTRACT BLOB:
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
REWORK SCOPE COMPLIANCE:
CASE-001:
CASE-002:
CASE-003:
CLEANUP:
ARTIFACT_NAME:
ARCHIVE_SHA256:
RETENTION / DOWNLOAD LOCATION:
CONCLUSION:
```
