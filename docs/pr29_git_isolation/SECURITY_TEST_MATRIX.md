# PR #29 — macierz testów bezpieczeństwa

Każdy wynik wskazuje dokładny SHA, run ID i konkretny dowód. Sam status `PASS` bez logu, trace, markera lub manifestu jest niekompletny.

| Wektor | Oczekiwane zachowanie | Test | SHA / run | Wynik | Dowód |
|---|---|---|---|---|---|
| `post-checkout` hook | marker nie powstaje | `test_executable_post_checkout_hook_cannot_run_on_host` | `ea3226dc` / `30767747711` | PASS | unit log |
| filtr `clean` | marker nie powstaje | `test_local_clean_filter_cannot_run_on_host` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| filtr `smudge` | marker nie powstaje | `test_local_smudge_filter_cannot_run_on_host` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| filtr `process` | proces nie startuje | `test_local_process_filter_cannot_start_on_host` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| `include.path` | konfiguracja nie jest ładowana | `test_include_path_cannot_load_executable_filter_configuration` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| `includeIf` | konfiguracja nie jest ładowana | `test_include_if_cannot_load_executable_filter_configuration` | `ea3226dc` / `30767747711` | RED | marker + failure log |
| fsmonitor | program nie startuje | istniejący test / rozszerzenie PENDING | PENDING | PENDING | trace |
| external diff | program nie startuje | test regresyjny PENDING | PENDING | PENDING | trace |
| textconv | program nie startuje | test regresyjny PENDING | PENDING | PENDING | trace |
| Git na wejściowym checkoutcie | brak procesu | `test_executor_never_runs_git_against_input_checkout_or_git_dir` | `ea3226dc` / `30767747711` | RED | 6 wywołań w failure log |
| Git na wejściowym `.git` przez `--git-dir` | brak procesu | test negatywny PENDING | PENDING | PENDING | exec trace |
| Git na wejściowym `.git` przez env | brak procesu | test negatywny PENDING | PENDING | PENDING | exec trace |
| Git wykryty przez cwd / katalog nadrzędny | brak procesu | test negatywny PENDING | PENDING | PENDING | exec trace |
| remote helper / skrypt potomny | brak wykonania kodu wejścia | test negatywny PENDING | PENDING | PENDING | exec trace |
| INPUT MODEL COMPLIANCE | wejście zgodne z ADR albo fail-closed | test modelu wejścia | PENDING | PENDING | report |
| OBJECT IDENTITY | commit, drzewa i bloby zgodne | test integralności | PENDING | PENDING | hashes |
| ORIGIN ANCHOR | pochodzenie zakotwiczone poza checkoutem | test ADR | PENDING | PENDING | acquisition log / signature |
| zmiana working tree | brak istotnych zmian | manifest | PENDING | PENDING | before / after |
| zmiana wejściowego `.git` | brak istotnych zmian | manifest bezpieczeństwa | PENDING | PENDING | before / after |
| CASE-001 | poprawny wynik | real run | `ea3226dc` / `30767747711` | PASS | sandbox job |
| CASE-002 | poprawny wynik | real run | `ea3226dc` / `30767747711` | PASS | sandbox job |
| CASE-003 | poprawny wynik | real run | `ea3226dc` / `30767747711` | PASS | sandbox job |
| source checkouts pinned and clean | dokładne HEAD i pusty status | workflow gate | `ea3226dc` / `30767747711` | PASS* | sandbox job |
| cleanup | brak pozostałych procesów i kontenerów | workflow gate | `ea3226dc` / `30767747711` | PASS | sandbox job |
| terminalny `PASS` | niedostępny | istniejące testy stanu | `ea3226dc` / `30767747711` | PASS | unit log |

`PASS*` przy kontroli źródeł potwierdza dotychczasowy warunek workflow. Nie dowodzi bezpieczeństwa samego `git status` wobec wrogich metadanych; nowy model musi zastąpić tę kontrolę manifestem lub repozytorium kontrolowanym zgodnie z ADR.

## Diagnostyka per polecenie

Dla Git `2.47.3` skrypt `evidence/diagnose_git_filter_surface.py` wykazał:

| Filtr | Polecenia uruchamiające testowany program |
|---|---|
| `clean` | `status`, `diff`, `add`, `commit` |
| `smudge` | `worktree add` |
| `process` | `status`, `worktree add`, `diff`, `add` |

Brak wykonania w tej diagnozie nie tworzy listy „bezpiecznych poleceń”. Nadrzędny invariant zabrania wszystkim procesom Executora używania wejściowego `.git`.

## Zasady aktualizacji

- Zakres macierzy może zostać rozszerzony na podstawie ADR lub nowego kontrprzykładu.
- Czerwony wynik na test-only SHA pozostaje jako dowód wykrywania podatności.
- Zielony wynik musi pochodzić z fixed implementation SHA.
- Wyniki baseline workflow `30766241419` są dowodem funkcjonalnym, nie dowodem izolacji filtrów Git.
