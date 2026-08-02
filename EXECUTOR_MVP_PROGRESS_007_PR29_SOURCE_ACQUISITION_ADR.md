# Executor MVP Progress 007 — PR #29 source acquisition ADR

## Status

```text
PR #29: REWORK
ADR DECISION SHA: bf18638caeb1a01cd2e14e625d72a20893a04bb3
CURRENT PR #29 COMMITS: 5
CURRENT PR #29 CHANGED FILES: 31
IMPLEMENTATION FIX: NOT STARTED
READY: NO
MERGE: NO
```

## Formalny zakres

Pierwotny zakres 21 plików został zastąpiony formalnym `REWORK_SCOPE_V2`:

```text
BASELINE_SCOPE:
21 pierwotnych plików runtime

REWORK_SCOPE_ADDITIONS:
6 nazwanych testów w istniejącym tests/test_pilot_git_isolation.py
10 plików docs/pr29_git_isolation/
ADR-001 osadzony w REWORK_PLAN.md

FUTURE_IMPLEMENTATION_WRITE_ALLOWLIST:
zamknięta lista ścieżek

UNAUTHORIZED_FILES:
każda inna ścieżka
```

Końcowa bramka zawiera `REWORK SCOPE COMPLIANCE: PASS / FAIL`.

## Wybrany model wejścia MVP

```text
MODEL: CONTROLLED_HTTPS_FETCH_V1
HOST: github.com
REPOSITORY: litrgratis-pixel/executor-pilot-target
LOCAL CHECKOUT: UNSUPPORTED / FAIL-CLOSED
OFFLINE BUNDLE: DEFERRED
ARBITRARY OBJECT STORE IMPORT: UNSUPPORTED
```

Źródło ma być pobierane przez dedykowany control-plane container do katalogu `run_dir`. Sieć pozyskania źródła jest oddzielna od workera; worker i sandbox nadal wymagają `network=false`.

## Toolchain

```text
IMAGE: alpine/git@sha256:0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd
PLATFORM: linux/amd64
GIT_BINARY_PATH: /usr/bin/git
GIT_VERSION: 2.54.0
```

Run ma blokować niezgodny digest, platformę, ścieżkę binarną lub wersję Git.

## Rozdzielone dowody

```text
INPUT MODEL COMPLIANCE:
tylko dokładny model CONTROLLED_HTTPS_FETCH_V1

OBJECT IDENTITY:
dokładny commit, root tree i blob PILOT_CONTRACT.md

ORIGIN ANCHOR:
kontrolowany HTTPS fetch z dokładnego allowlistowanego endpointu
```

Hash obiektu potwierdza jego tożsamość treściową, nie pochodzenie. Origin anchor nie dowodzi autorstwa commita.

## Stan diagnostyki

```text
CLEAN / SMUDGE / PROCESS DIAGNOSTICS:
COMPLETE FOR TESTED COMMANDS

GENERAL HOST GIT EXECUTION SURFACE:
PARTIAL — REMAINING TESTS DERIVE FROM ADR-001
```

## Evidence przed finalnym review

Workflow musi zachować artefakt:

```text
pr29-git-isolation-<full-head-sha>
```

z pełnymi logami, process trace, markerami, manifestami, acquisition evidence, raportami CASE-001–003, wersjami narzędzi i cleanupem.

## Następna bramka

```text
ADR DECISION SHA
→ minimal implementation within REWORK_SCOPE_V2
→ GREEN_RUN_ID
→ adversarial acceptance
→ independent review
→ ACCEPT / REWORK / STOP
```

Nie wolno rozpoczynać AI workera, M3, CASE-004 ani frameworka providerów przed formalnym `ACCEPT` PR #29.
