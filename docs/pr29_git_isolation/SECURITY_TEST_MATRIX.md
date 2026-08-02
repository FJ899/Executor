# PR #29 — macierz testów bezpieczeństwa

Każdy wynik musi wskazywać dokładny SHA, run ID i konkretny dowód. Sam status `PASS` bez logu, trace, markera lub manifestu jest niekompletny.

| Wektor | Oczekiwane zachowanie | Test | SHA / run | Wynik | Dowód |
|---|---|---|---|---|---|
| `post-checkout` hook | marker nie powstaje | istniejący test izolacji | PENDING | PENDING | log |
| filtr `clean` | marker nie powstaje | nowy test | PENDING | PENDING | marker + trace |
| filtr `smudge` | marker nie powstaje | nowy test | PENDING | PENDING | marker + trace |
| filtr `process` | proces nie startuje | nowy test | PENDING | PENDING | trace |
| `include.path` | konfiguracja nie jest ładowana | nowy test | PENDING | PENDING | marker + trace |
| `includeIf` | konfiguracja nie jest ładowana | nowy test | PENDING | PENDING | marker + trace |
| fsmonitor | program nie startuje | test regresyjny | PENDING | PENDING | trace |
| external diff | program nie startuje | test regresyjny | PENDING | PENDING | trace |
| textconv | program nie startuje | test regresyjny | PENDING | PENDING | trace |
| Git na wejściowym checkoutcie | brak procesu | test wrappera + trace | PENDING | PENDING | exec trace |
| Git na wejściowym `.git` przez `--git-dir` | brak procesu | test negatywny | PENDING | PENDING | exec trace |
| Git na wejściowym `.git` przez env | brak procesu | test negatywny | PENDING | PENDING | exec trace |
| Git wykryty przez cwd / katalog nadrzędny | brak procesu | test negatywny | PENDING | PENDING | exec trace |
| remote helper / skrypt potomny | brak wykonania kodu wejścia | test negatywny | PENDING | PENDING | exec trace |
| INPUT MODEL COMPLIANCE | wejście zgodne z ADR albo fail-closed | test modelu wejścia | PENDING | PENDING | report |
| OBJECT IDENTITY | commit, drzewa i bloby zgodne | test integralności | PENDING | PENDING | hashes |
| ORIGIN ANCHOR | pochodzenie zakotwiczone poza checkoutem | test ADR | PENDING | PENDING | acquisition log / signature |
| zmiana working tree | brak istotnych zmian | manifest | PENDING | PENDING | before / after |
| zmiana wejściowego `.git` | brak istotnych zmian | manifest bezpieczeństwa | PENDING | PENDING | before / after |
| CASE-001 | poprawny wynik | real run | PENDING | PENDING | report |
| CASE-002 | poprawny wynik | real run | PENDING | PENDING | report |
| CASE-003 | poprawny wynik | real run | PENDING | PENDING | report |
| cleanup | brak pozostałych procesów i kontenerów | test cleanupu | PENDING | PENDING | log |
| terminalny `PASS` | niedostępny | test stanu | PENDING | PENDING | log |

## Zasady aktualizacji

- Zakres macierzy może zostać rozszerzony wyłącznie na podstawie wybranego ADR lub nowego kontrprzykładu.
- Czerwony wynik na test-only SHA pozostaje w macierzy jako dowód wykrywania podatności.
- Zielony wynik musi pochodzić z fixed implementation SHA.
- Wyniki starego workflow `30766241419` są dowodem funkcjonalnym baseline, nie dowodem izolacji filtrów Git.
