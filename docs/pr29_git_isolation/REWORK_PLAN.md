# PR #29 — plan REWORK izolacji hostowych operacji Git

## Stan faz

```text
FAZA 1 — EVIDENCE FREEZE: COMPLETE
FAZA 2A — CLEAN/SMUDGE/PROCESS DIAGNOSTICS: COMPLETE FOR TESTED COMMANDS
FAZA 2B — GENERAL HOST GIT EXECUTION SURFACE: PARTIAL
FAZA 3 — TEST-ONLY SHA + RED RUN: COMPLETE
FAZA 4 — ADR-001 INPUT MODEL: ACCEPTED FOR IMPLEMENTATION
FAZA 5 — IMPLEMENTATION: NOT STARTED
```

Faza 2B pozostaje częściowa. Dalsze testy powierzchni wykonania wynikają z ADR-001; nie należy bez potrzeby rozwijać nieskończonej listy przed wyborem modelu wejścia.

## Faza 1 — zamrożenie dowodów

Zakończona. PR pozostaje draftem, baseline SHA, reproduktor, output, wersje Git i czerwony run są zapisane. Nie wolno przepisywać historii.

## Faza 2 — diagnostyka

Zakończona dla testowanej powierzchni filtrów:

```text
clean: status, diff, add, commit
smudge: worktree add
process: status, worktree add, diff, add
```

Nadal wymagają pokrycia zgodnie z ADR:

- fsmonitor;
- external diff;
- textconv;
- `--git-dir` i `--work-tree`;
- `GIT_DIR`, `GIT_WORK_TREE` i inne zmienne Git;
- wykrycie repozytorium przez cwd;
- niekontrolowany remote helper;
- program potomny uruchamiający Git.

Wyniki per polecenie są diagnostyczne. Nadrzędny zakaz używania wejściowego `.git` nie zależy od wersji Git ani od tego, czy konkretne polecenie uruchomiło program w jednym teście.

## Faza 3 — test-only commit i czerwony run

Zakończona.

```text
VULNERABLE_IMPLEMENTATION_SHA: 514ba20d67bd415e438440c62f47307709177a7f
TEST_ONLY_SHA: ea3226dc2836d6287af7a080d12d3adeb7787298
RED_RUN_ID: 30767747711
```

Naprawa nie znajduje się w test-only SHA.

# Faza 4 — ADR-001: CONTROLLED_HTTPS_FETCH_V1

## Status

```text
ADR STATUS: ACCEPTED FOR PR #29 IMPLEMENTATION
DECISION SCOPE: MVP / CASE-001–003 ONLY
ALTERNATIVE INPUT MODELS: DEFERRED
```

ADR jest częścią tego dokumentu. Nie powstaje szósty dokument procesu.

## Kontekst

Nieufny lokalny checkout i jego `.git` mogą uruchamiać programy na hoście przed Dockerem. Punktowe wyłączanie kolejnych mechanizmów Git nie ustanawia stabilnej granicy bezpieczeństwa.

PR #29 potrzebuje jednego, wąskiego modelu wejścia. Równoległe wdrażanie fresh fetch, bundle i lokalnego checkoutu podwoiłoby powierzchnię bezpieczeństwa i testowania.

## Rozważone warianty

### A. CONTROLLED HTTPS FETCH

Executor tworzy repozytorium w `run_dir` i pobiera dokładny commit z jednego allowlistowanego repozytorium przez HTTPS, używając przypiętego narzędzia Git.

### B. HASHED IMMUTABLE GIT BUNDLE

Wąski format offline z SHA-256 bundle, pełnym SHA commita i zewnętrznym origin anchor. Rozsądny wariant przyszły, lecz nie jest wdrażany w PR #29.

### C. Lokalny checkout lub dowolny object store

Odrzucone dla MVP. Zbyt szeroki format, niepewna konfiguracja, alternates, worktrees, commondir, TOCTOU i niejednoznaczne pochodzenie.

## Decyzja

Wybrano `CONTROLLED_HTTPS_FETCH_V1`.

```text
ALLOWLISTED HOST: github.com
ALLOWLISTED REPOSITORY: litrgratis-pixel/executor-pilot-target
ALLOWED SCHEME: https
OBJECT FORMAT: sha1
EXPECTED COMMIT FORMAT: exactly 40 lowercase hexadecimal characters
EXPECTED CONTRACT BLOB FORMAT: exactly 40 lowercase hexadecimal characters
LOCAL CHECKOUT INPUT: unsupported
OFFLINE BUNDLE INPUT: unsupported in PR #29
ARBITRARY OBJECT STORE INPUT: unsupported
```

URL źródła nie jest przyjmowany od użytkownika. Executor buduje dokładnie:

```text
https://github.com/litrgratis-pixel/executor-pilot-target.git
```

z kanonicznej wartości kontraktu. Każda inna nazwa repozytorium, host, schemat lub forma URL jest odrzucana przed uruchomieniem narzędzia pozyskania.

## Granice sieci

```text
SOURCE ACQUISITION NETWORK POLICY:
network enabled only for the dedicated acquisition container and exact HTTPS source

WORKER EXECUTION NETWORK POLICY:
network=false without exception
```

Sieć control plane nie odblokowuje sieci workera ani sandboxu.

## Polityka transportu

Dozwolone:

- wyłącznie HTTPS;
- dokładny allowlistowany host i repository path;
- pełny SHA commita;
- weryfikacja certyfikatu TLS przez trust store przypiętego obrazu;
- fetch bez tagów i bez submodules;
- repozytorium docelowe wyłącznie pod `run_dir`.

Zabronione fail-closed:

- lokalne ścieżki;
- `file://`;
- `ext::`;
- SSH, SCP-like syntax i `GIT_SSH_COMMAND`;
- protokół `git://`;
- HTTP bez TLS;
- dowolny URL przekazany przez użytkownika;
- credential helpers;
- askpass i terminal prompt;
- automatyczne submodules;
- LFS smudge;
- alternatywny remote helper spoza przypiętego toolchainu;
- cross-host redirect;
- hostowe `HOME`, `XDG_CONFIG_HOME`, `.gitconfig`, credentials i SSH agent.

Wymagane ustawienia obejmują co najmniej:

```text
GIT_CONFIG_NOSYSTEM=1
GIT_CONFIG_GLOBAL=/dev/null
GIT_ATTR_NOSYSTEM=1
GIT_TERMINAL_PROMPT=0
GIT_ASKPASS=/bin/false
SSH_ASKPASS=/bin/false
GIT_SSH_COMMAND=<unset>
GIT_LFS_SKIP_SMUDGE=1
```

oraz usunięcie wszystkich odziedziczonych `GIT_*` przed dodaniem jawnej allowlisty zmiennych.

Konfiguracja Git musi wymuszać:

```text
protocol.allow=never
protocol.https.allow=always
protocol.file.allow=never
protocol.ext.allow=never
protocol.ssh.allow=never
protocol.git.allow=never
credential.helper=
fetch.recurseSubmodules=false
submodule.recurse=false
http.followRedirects=false
```

Dozwolony jest jedynie HTTPS helper dostarczony wewnątrz przypiętego toolchainu. PATH kontenera nie może zawierać hostowych ani zamontowanych katalogów wykonywalnych.

## Przypięty toolchain Git

```text
TOOL IMAGE: alpine/git@sha256:0448d24b454392f9d115c6784343899e9d35a32de0ddc39a745263db34df94dd
PLATFORM: linux/amd64
EXPECTED GIT_BINARY_PATH: /usr/bin/git
EXPECTED GIT_VERSION: 2.54.0
```

Przed fetch run zapisuje:

```text
GIT_BINARY_PATH
GIT_VERSION
GIT_BUILD_OR_IMAGE_DIGEST
PLATFORM
```

Niezgodność blokuje run przed pozyskaniem źródła.

## INPUT MODEL COMPLIANCE

`PASS` wymaga:

- kontrakt wskazuje dokładnie allowlistowane repozytorium;
- commit i blob kontraktu są pełnymi 40-znakowymi identyfikatorami SHA-1;
- nie przekazano lokalnego checkoutu, bundle ani object store;
- katalog pozyskania jest nowy, znajduje się pod `run_dir` i nie ma rodzica będącego repozytorium Git;
- wszystkie niewspierane warianty są odrzucane przed uruchomieniem kontenera acquisition.

## OBJECT IDENTITY

`PASS` oznacza wyłącznie tożsamość treściową:

1. `FETCH_HEAD` jest dokładnie oczekiwanym pełnym SHA;
2. pobrany obiekt jest commitem;
3. checkout detached HEAD wskazuje dokładnie oczekiwany commit;
4. root tree jest odczytany z tego commita i zapisany w evidence;
5. `PILOT_CONTRACT.md` w oczekiwanym commicie ma dokładnie przypięty blob SHA;
6. `git fsck --strict` dla kontrolowanego repozytorium nie wykrywa niespójności wymaganych obiektów;
7. commit, tree i contract blob użyte później są ponownie sprawdzane przed utworzeniem wyniku.

`OBJECT IDENTITY` nie jest dowodem pochodzenia.

## ORIGIN ANCHOR

`PASS` oznacza:

- URL został skonstruowany przez Executora z allowlistowanego `owner/repository`, nie odczytany z wejściowego `.git/config`;
- fetch został wykonany przypiętym toolchainem;
- transport był HTTPS do dokładnego hosta `github.com` i dokładnej ścieżki repozytorium;
- certyfikat TLS został zweryfikowany, a wyłączenie weryfikacji jest niedostępne;
- acquisition log zapisuje kanoniczny URL bez sekretów, pełny oczekiwany SHA, pobrany SHA, image digest i wersję Git;
- żaden lokalny `origin` nie uczestniczy w decyzji.

Ten anchor dowodzi, że kontrolowany klient otrzymał obiekty z allowlistowanego endpointu GitHub. Nie dowodzi autorstwa commita ani intencji jego twórcy.

## INPUT IMMUTABILITY

Lokalny checkout użytkownika nie jest wejściem wspieranym. Dla modelu V1 nie wykonuje się na nim Git i nie przekazuje się go do acquisition container.

Niezmienność dotyczy:

- bajtów kontraktu i policy snapshotu;
- katalogu acquisition po zakończeniu fetch;
- manifestu plików checkoutu kontrolowanego przed workerem;
- istotnego stanu wynikowego po runie.

Manifest obejmuje zawartość, obecność, typ wpisu, cel symlinka i istotne tryby. Nie obejmuje domyślnie atime ani nieistotnych timestampów. Manifest wykrywa naruszenie; repozytorium acquisition powinno dodatkowo być niedostępne do zapisu dla workera.

## Decyzje odrzucone

- Nie implementować jednocześnie Git bundle.
- Nie importować dowolnego local object store.
- Nie uznawać lokalnego `origin` za dowód.
- Nie uruchamiać hostowego Git na lokalnym checkoutcie.
- Nie naprawiać filtrów przez zgadywanie ich nazw.

# REWORK_SCOPE_V2 — dozwolony zakres implementacji

Po ADR wolno modyfikować wyłącznie:

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

Każda potrzeba zmiany innego pliku zatrzymuje implementację do czasu jawnego `REWORK_SCOPE_V3`.

# Testy odblokowane przez ADR-001

Nie są dodawane w commicie ADR. Następny test/implementation etap musi objąć:

1. akceptację dokładnego allowlistowanego HTTPS source;
2. odrzucenie innego hosta i repozytorium;
3. odrzucenie `file://`, `ext::`, SSH, `git://`, HTTP i lokalnej ścieżki;
4. odrzucenie dowolnego URL użytkownika;
5. odrzucenie lokalnego checkoutu nawet przy poprawnym origin i HEAD;
6. wyłączenie credential helpers, askpass, SSH agent i hostowego HOME;
7. zakaz submodules i LFS smudge;
8. odrzucenie cross-host redirect;
9. wymuszenie dokładnego image digest, platformy, ścieżki Git i wersji Git;
10. niezgodny oczekiwany commit;
11. niezgodny blob `PILOT_CONTRACT.md`;
12. brak lub niekompletny pobrany obiekt;
13. repozytorium acquisition wyłącznie pod `run_dir`;
14. brak procesu Git używającego wejściowego checkoutu przez cwd, argument lub env;
15. brak hostowego helpera lub programu potomnego;
16. fsmonitor, external diff i textconv nie uruchamiają programu wejścia;
17. przerwanie fetch pozostawia stan fail-closed i cleanup;
18. CASE-001–003 działają z nowym modelem;
19. worker sandbox nadal ma `network=false`;
20. brak terminalnego `PASS`.

# Surowe evidence CI

Przed finalnym review workflow musi zachować artefakt:

```text
ARTIFACT_NAME: pr29-git-isolation-<full-head-sha>
```

Archiwum zawiera co najmniej:

- pełny unit/integration log;
- process trace;
- markery;
- manifest przed i po;
- acquisition log;
- `GIT_BINARY_PATH`, `GIT_VERSION`, image digest i platformę;
- raporty CASE-001–003;
- Docker cleanup log;
- finalną macierz wyników.

`EVIDENCE_LOG.md` zapisuje `ARTIFACT_NAME`, `RUN_ID`, `HEAD_SHA`, `ARCHIVE_SHA256` oraz retention/download location.

# Dalsza kolejność

```text
ADR DECISION COMMIT
→ implementation commit
→ GREEN_RUN_ID
→ adversarial acceptance
→ independent review
→ ACCEPT / REWORK / STOP
```
