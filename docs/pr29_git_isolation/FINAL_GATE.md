# PR #29 — końcowa bramka

Wypełnić wyłącznie dla dokładnego `REVIEWED SHA`. Każde `PASS` musi mieć odwołanie do macierzy testów, dziennika dowodów i surowego artefaktu CI.

```text
PR: #29
REVIEWED SHA: <fixed SHA>
ADR DECISION SHA: <ADR commit SHA>
GREEN RUN ID: <run ID>
RAW EVIDENCE ARTIFACT: pr29-git-isolation-<full-reviewed-sha>
ARCHIVE SHA256: <sha256>

REWORK SCOPE COMPLIANCE:
PASS / FAIL

INPUT MODEL COMPLIANCE:
PASS / FAIL

OBJECT IDENTITY:
PASS / FAIL

ORIGIN ANCHOR:
PASS / FAIL

GIT INPUT ISOLATION:
PASS / FAIL

INPUT IMMUTABILITY:
PASS / FAIL

PINNED GIT TOOLCHAIN:
PASS / FAIL

CASE-001:
PASS / FAIL

CASE-002:
PASS / FAIL

CASE-003:
PASS / FAIL

DEFINED ADVERSARIAL SUITE:
PASS / FAIL

FALSE SUCCESS FOUND WITHIN DEFINED THREAT MODEL:
YES / NO

FINAL DECISION:
ACCEPT / REWORK / STOP
```

## REWORK SCOPE COMPLIANCE

`PASS` wymaga:

- 21 plików baseline odpowiada formalnemu `BASELINE_SCOPE`;
- dodatkowe pliki odpowiadają dokładnie `REWORK_SCOPE_ADDITIONS`;
- implementacja zmienia wyłącznie `FUTURE_IMPLEMENTATION_WRITE_ALLOWLIST`;
- nie występuje żaden `UNAUTHORIZED_FILE`;
- nie przepisano historii baseline, test-only ani czerwonego runu.

Każdy dodatkowy plik oznacza `FAIL`, chyba że przed jego zmianą formalnie przyjęto `REWORK_SCOPE_V3`.

## ACCEPT

Tylko gdy:

- `REWORK SCOPE COMPLIANCE` jest `PASS`;
- wejście spełnia jedyny wspierany model `CONTROLLED_HTTPS_FETCH_V1`;
- lokalny checkout, bundle i dowolny object store są odrzucane fail-closed;
- exact commit, root tree i blob `PILOT_CONTRACT.md` potwierdzają `OBJECT IDENTITY`;
- kontrolowany HTTPS fetch do dokładnego allowlistowanego endpointu potwierdza `ORIGIN ANCHOR`;
- source acquisition używa dokładnego przypiętego image digest, platformy, binarki i wersji Git;
- żaden proces uruchomiony przez Executora nie otrzymuje wejściowego checkoutu ani jego `.git` przez cwd, argument, env lub program potomny;
- credential helpers, askpass, SSH, local/file/ext/git/http protocols, submodules, LFS smudge i niekontrolowane remote helpers są zablokowane;
- wszystkie kontrprzykłady i klasy ataku wymagane przez ADR-001 oraz macierz są zablokowane;
- acquisition repository i istotne wejścia pozostają niezmienione zgodnie z manifestem;
- worker sandbox nadal ma `network=false`;
- CASE-001–003 przechodzą na jednym fixed SHA;
- pełne CI jest zielone dla `REVIEWED SHA`;
- raw evidence artifact zawiera logi, trace, markery, manifesty, raporty przypadków, wersje narzędzi i cleanup;
- nie znaleziono false success w zdefiniowanym modelu zagrożeń.

Formuła dowodowa:

```text
ALL ADR-001 AND ACCEPTANCE-MATRIX ATTACK CLASSES BLOCKED
NO FALSE SUCCESS FOUND WITHIN THE DEFINED THREAT MODEL
```

Nie wolno twierdzić, że udowodniono brak wszystkich możliwych false success poza zdefiniowanym modelem.

## REWORK

Gdy:

- zakres jest naruszony;
- naprawa jest częściowa;
- toolchain nie jest dokładnie przypięty;
- evidence jest niekompletne;
- raw artifact jest niedostępny lub niepowiązany z pełnym SHA;
- macierz nadal ujawnia wykonalny wektor;
- wynik zależy od niekontrolowanej wersji Git lub hostowego środowiska.

## STOP

Gdy bezpieczne rozwiązanie wymaga:

- zaufania do wejściowego `.git`;
- osłabienia sandboxu;
- nieweryfikowalnego pochodzenia obiektów;
- obsługi wielu modeli wejścia w PR #29;
- nieproporcjonalnie dużej platformy względem wartości pilota.
