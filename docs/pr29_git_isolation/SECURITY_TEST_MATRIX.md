# PR #29 — macierz testów bezpieczeństwa

Każdy wynik wskazuje dokładny SHA, run ID i konkretny dowód. Sam status `PASS` bez logu, trace, markera, manifestu lub artefaktu jest niekompletny.

## Status powierzchni

```text
CLEAN / SMUDGE / PROCESS DIAGNOSTICS:
COMPLETE FOR TESTED COMMANDS

GENERAL HOST GIT EXECUTION SURFACE:
PARTIAL — REMAINING TESTS DERIVE FROM ADR-001
```

| Wektor | Oczekiwane zachowanie | Test | SHA / run | Wynik | Dowód |
|---|---|---|---|---|---|
| `post-checkout` hook | marker nie powstaje | `test_executable_post_checkout_hook_cannot_run_on_host` | `ea3226dc` / `30767747711` | PASS | unit log |
| filtr `clean` | marker nie powstaje | `test_local_clean_filter_cannot_run_on_host` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| filtr `smudge` | marker nie powstaje | `test_local_smudge_filter_cannot_run_on_host` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| filtr `process` | proces nie startuje | `test_local_process_filter_cannot_start_on_host` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| `include.path` | konfiguracja nie jest ładowana | `test_include_path_cannot_load_executable_filter_configuration` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| `includeIf` | konfiguracja nie jest ładowana | `test_include_if_cannot_load_executable_filter_configuration` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| Git na wejściowym checkoutcie | brak procesu | `test_executor_never_runs_git_against_input_checkout_or_git_dir` | `ea3226dc` / `30767747711` | RED | 6 wywołań w failure log |
| CASE-001 | poprawny wynik | real run | `ea3226dc` / `30767747711` | PASS | sandbox job |
| CASE-002 | poprawny wynik | real run | `ea3226dc` / `30767747711` | PASS | sandbox job |
| CASE-003 | poprawny wynik | real run | `ea3226dc` / `30767747711` | PASS | sandbox job |
| cleanup | brak pozostałych kontenerów | workflow gate | `ea3226dc` / `30767747711` | PASS | sandbox job |
| terminalny `PASS` | niedostępny | istniejące testy stanu | `ea3226dc` / `30767747711` | PASS | unit log |

## Testy wymagane przez ADR-001

| Wektor | Oczekiwane zachowanie | Planowany dowód | Status |
|---|---|---|---|
| REWORK SCOPE COMPLIANCE | zmienione wyłącznie ścieżki z `REWORK_SCOPE_V2` | porównanie changed files + commit diff | PENDING |
| allowlist host/repository | akceptowane wyłącznie `github.com/litrgratis-pixel/executor-pilot-target` | acquisition report | PENDING |
| dowolny URL użytkownika | odrzucony przed uruchomieniem toolchainu | negative test | PENDING |
| lokalny checkout | `UNSUPPORTED / FAIL-CLOSED` | negative test + brak procesu Git | PENDING |
| lokalna ścieżka / `file://` | odrzucone | negative tests | PENDING |
| `ext::` | odrzucone | negative test | PENDING |
| SSH / SCP-like / `git://` / HTTP | odrzucone | negative tests | PENDING |
| cross-host redirect | odrzucony | transport test | PENDING |
| credential helper / askpass | nieuruchomione | process trace | PENDING |
| SSH command / agent | nieużyte | env + process trace | PENDING |
| submodules | niepobierane | acquisition log + filesystem manifest | PENDING |
| LFS smudge | nieuruchomiony | process trace + marker | PENDING |
| niekontrolowany remote helper | nieuruchomiony | restricted PATH + process trace | PENDING |
| przypięty image digest | dokładny `sha256:0448d24...` | container inspect / acquisition report | PENDING |
| platforma | dokładnie `linux/amd64` | container inspect | PENDING |
| Git binary path | dokładnie `/usr/bin/git` | acquisition report | PENDING |
| Git version | dokładnie `2.54.0` | acquisition report | PENDING |
| INPUT MODEL COMPLIANCE | tylko `CONTROLLED_HTTPS_FETCH_V1` | contract validation report | PENDING |
| OBJECT IDENTITY — commit | `FETCH_HEAD` i detached HEAD równe oczekiwanemu SHA | hashes + log | PENDING |
| OBJECT IDENTITY — tree | root tree związany z oczekiwanym commitem | hash | PENDING |
| OBJECT IDENTITY — contract blob | dokładny blob `PILOT_CONTRACT.md` | hash | PENDING |
| object integrity | wymagane obiekty przechodzą `git fsck --strict` | raw log | PENDING |
| ORIGIN ANCHOR | kontrolowany HTTPS fetch do dokładnego endpointu | acquisition log | PENDING |
| acquisition under `run_dir` | brak repo poza katalogiem runu | path trace + manifest | PENDING |
| `--git-dir` / `--work-tree` do wejścia | brak procesu | exec trace | PENDING |
| `GIT_DIR` / `GIT_WORK_TREE` | brak wskazania wejścia | sanitized env + exec trace | PENDING |
| repo wykryte przez cwd | brak cwd wewnątrz nieufnego checkoutu | exec trace | PENDING |
| program potomny uruchamiający Git | brak nieautoryzowanego exec | exec trace | PENDING |
| fsmonitor | program wejścia nie startuje | marker + exec trace | PENDING |
| external diff | program wejścia nie startuje | marker + exec trace | PENDING |
| textconv | program wejścia nie startuje | marker + exec trace | PENDING |
| przerwany fetch | fail-closed i cleanup | interruption test | PENDING |
| niepełny / zły commit | run zablokowany | negative test | PENDING |
| zły contract blob | run zablokowany | negative test | PENDING |
| acquisition immutability | manifest istotnych wpisów stabilny | before / after | PENDING |
| worker network | `network=false` | Docker command + test | PENDING |
| raw CI evidence | artefakt związany z pełnym SHA | artifact metadata + archive SHA-256 | PENDING |
| CASE-001–003 po naprawie | wszystkie zielone na fixed SHA | reports + raw logs | PENDING |

## Diagnostyka per polecenie

Dla Git `2.47.3` skrypt `evidence/diagnose_git_filter_surface.py` wykazał:

| Filtr | Polecenia uruchamiające testowany program |
|---|---|
| `clean` | `status`, `diff`, `add`, `commit` |
| `smudge` | `worktree add` |
| `process` | `status`, `worktree add`, `diff`, `add` |

Brak wykonania w tej diagnozie nie tworzy listy „bezpiecznych poleceń”.

## Zasady aktualizacji

- Czerwony wynik na test-only SHA pozostaje dowodem wykrywania podatności.
- Zielony wynik musi pochodzić z fixed implementation SHA.
- Testy ADR nie są dodawane w commicie decyzyjnym.
- Każdy nowy plik poza `REWORK_SCOPE_V2` powoduje `REWORK SCOPE COMPLIANCE: FAIL`.
- Wyniki baseline workflow są dowodem funkcjonalnym, nie dowodem izolacji.
