# PR #29 — Karta bramki REWORK

```text
PR: #29
BASELINE SHA: 514ba20d67bd415e438440c62f47307709177a7f
DOCUMENTATION SHA: 9b71726eadd152984bd906bde2d8f0f8cd96dc39
TEST-ONLY SHA: ea3226dc2836d6287af7a080d12d3adeb7787298
RED RUN ID: 30767747711
PRE-ADR HEAD: 75943321535b872a7cd242cd31e467a90df9d1cd

DECISION: REWORK
READY: NO
MERGE: NO
STOP: NO
CURRENT CI: RED BY DESIGN
IMPLEMENTATION FIX: NOT STARTED
```

## Blocker

Hostowe operacje Git uruchamiają lokalne filtry `clean`, `smudge` i `process` oraz konfiguracje wczytane przez `include.path` i `includeIf` z metadanych wejściowego checkoutu.

Test-only run na Git `2.54.0` potwierdził sześć oczekiwanych porażek bezpieczeństwa, podczas gdy realne CASE-001–003 oraz Docker pozostały zielone. Funkcjonalność pilota działa, ale obowiązkowa izolacja hosta jest niespełniona.

## Status diagnostyki

```text
CLEAN / SMUDGE / PROCESS DIAGNOSTICS:
COMPLETE FOR TESTED COMMANDS

GENERAL HOST GIT EXECUTION SURFACE:
PARTIAL — REMAINING TESTS DERIVE FROM ADR
```

Nie wolno skracać tego statusu do `FAZA 2: COMPLETE`.

## Niezmiennik bezpieczeństwa

Przed utworzeniem repozytorium kontrolowanego przez Executora nie wolno uruchamiać Git ani kodu pochodzącego z repozytorium przeciwko wejściowemu checkoutowi lub jego `.git`.

Po utworzeniu repozytorium kontrolowanego wszystkie operacje Git muszą działać wyłącznie na ścieżkach należących do katalogu runu Executora.

Zakaz obejmuje przekazanie wejścia przez cwd, `-C`, `--git-dir`, `--work-tree`, zmienne `GIT_*`, automatyczne wykrywanie `.git`, skrypty pomocnicze, remote helpers i programy potomne.

## REWORK_SCOPE_V2

### BASELINE_SCOPE — 21 pierwotnych plików

```text
.github/workflows/verify.yml
PILOT_CASE_001_VERTICAL_SLICE.md
PILOT_CASE_002_VERTICAL_SLICE.md
PILOT_CASE_003_VERTICAL_SLICE.md
PILOT_RUNTIME_CONSOLIDATION.md
executor/pilot_case_001.py
executor/pilot_case_002.py
executor/pilot_case_003.py
executor/pilot_cli.py
executor/pilot_core.py
executor/repository_snapshot.py
executor/sandbox/pilot.py
pyproject.toml
tests/test_pilot_case_001.py
tests/test_pilot_case_001_integration.py
tests/test_pilot_case_002.py
tests/test_pilot_case_002_integration.py
tests/test_pilot_case_003.py
tests/test_pilot_case_003_integration.py
tests/test_pilot_cli.py
tests/test_pilot_git_isolation.py
```

### REWORK_SCOPE_ADDITIONS — istniejące artefakty

Nowe testy są dozwolone wyłącznie w `tests/test_pilot_git_isolation.py`:

```text
test_executor_never_runs_git_against_input_checkout_or_git_dir
test_include_if_cannot_load_executable_filter_configuration
test_include_path_cannot_load_executable_filter_configuration
test_local_clean_filter_cannot_run_on_host
test_local_process_filter_cannot_start_on_host
test_local_smudge_filter_cannot_run_on_host
```

Nowe pliki dozwolone w obecnym REWORK:

```text
docs/pr29_git_isolation/GATE_CARD.md
docs/pr29_git_isolation/REWORK_PLAN.md
docs/pr29_git_isolation/SECURITY_TEST_MATRIX.md
docs/pr29_git_isolation/EVIDENCE_LOG.md
docs/pr29_git_isolation/FINAL_GATE.md
docs/pr29_git_isolation/evidence/EXECUTOR_PR29_VERIFICATION.md
docs/pr29_git_isolation/evidence/diagnose_git_filter_surface.py
docs/pr29_git_isolation/evidence/git_filter_surface_output.csv
docs/pr29_git_isolation/evidence/reproduce_git_filter_escape.sh
docs/pr29_git_isolation/evidence/reproduction_output.txt
```

ADR-001 jest częścią `REWORK_PLAN.md`; nie powstaje szósty dokument procesu.

### FUTURE_IMPLEMENTATION_WRITE_ALLOWLIST

Po przyjęciu ADR wolno zmienić wyłącznie:

```text
.github/workflows/verify.yml
executor/pilot_core.py
executor/pilot_cli.py
executor/repository_snapshot.py
executor/source_acquisition.py
tests/test_pilot_case_001.py
tests/test_pilot_case_002.py
tests/test_pilot_case_003.py
tests/test_pilot_case_001_integration.py
tests/test_pilot_case_002_integration.py
tests/test_pilot_case_003_integration.py
tests/test_pilot_cli.py
tests/test_pilot_git_isolation.py
tests/test_pilot_source_acquisition.py
docs/pr29_git_isolation/GATE_CARD.md
docs/pr29_git_isolation/REWORK_PLAN.md
docs/pr29_git_isolation/SECURITY_TEST_MATRIX.md
docs/pr29_git_isolation/EVIDENCE_LOG.md
docs/pr29_git_isolation/FINAL_GATE.md
```

Każdy inny plik jest `UNAUTHORIZED_FILE` i wymaga jawnego `REWORK_SCOPE_V3` przed zmianą.

## ADR-001 — skrót decyzji

```text
MVP INPUT MODEL:
CONTROLLED_HTTPS_FETCH_V1

ALLOWLISTED HOST:
github.com

ALLOWLISTED REPOSITORY:
litrgratis-pixel/executor-pilot-target

UNTRUSTED LOCAL CHECKOUT:
UNSUPPORTED / FAIL-CLOSED

OFFLINE BUNDLE:
DEFERRED / NOT IMPLEMENTED IN PR #29

ARBITRARY OBJECT STORE IMPORT:
UNSUPPORTED
```

Pozyskanie źródła odbywa się w osobnym control-plane containerze. Sieć tego etapu może być włączona wyłącznie dla kontrolowanego HTTPS fetch. Worker i sandbox nadal mają `network=false`.

## Przypięty Git control plane

```text
TOOL IMAGE:
alpine/git@sha256:0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd

PLATFORM:
linux/amd64

EXPECTED GIT VERSION:
2.54.0

EXPECTED GIT BINARY PATH:
/usr/bin/git
```

Run musi fail-closed, jeżeli obraz, platforma, ścieżka binarna lub wynik `git --version` są inne.

## Rozdzielone właściwości

```text
INPUT MODEL COMPLIANCE:
Czy wejście spełnia CONTROLLED_HTTPS_FETCH_V1?

INPUT IMMUTABILITY:
Czy kontrakt i wyniki pozyskania pozostały niezmienione w istotnym stanie bezpieczeństwa?

OBJECT IDENTITY:
Czy użyto dokładnego commita, drzewa i wymaganego bloba kontraktu?

ORIGIN ANCHOR:
Czy obiekty zostały pobrane przez kontrolowany HTTPS fetch z dokładnego allowlistowanego repozytorium?
```

URL `origin` z wejściowego `.git/config` nie jest dowodem pochodzenia.

## Exit criteria

- `REWORK SCOPE COMPLIANCE` jest `PASS`;
- ADR-001 pozostaje jedynym wspieranym modelem wejścia MVP;
- implementacja używa przypiętego Git control plane;
- wszystkie testy odblokowane przez ADR są zielone na jednym fixed SHA;
- CASE-001–003 są zielone;
- surowe evidence CI jest zachowane jako artefakt związany z pełnym SHA;
- wykonano niezależne review fixed SHA;
- `NO FALSE SUCCESS FOUND WITHIN THE DEFINED THREAT MODEL`.

Dozwolona końcowa decyzja: `ACCEPT`, `REWORK` albo `STOP`.
