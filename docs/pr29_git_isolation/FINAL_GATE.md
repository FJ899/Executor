# PR #29 — końcowa bramka

Wypełnić wyłącznie dla dokładnego `REVIEWED SHA`. Każde `PASS` musi mieć odwołanie do macierzy testów i dziennika dowodów.

```text
PR: #29
REVIEWED SHA: <new SHA>

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

## ACCEPT

Tylko gdy:

- wejście spełnia model wybrany w ADR;
- tożsamość commitów, drzew i blobów została potwierdzona;
- pochodzenie zostało zakotwiczone mechanizmem z ADR;
- żaden proces uruchomiony przez Executora nie otrzymuje wejściowego checkoutu ani jego `.git` jako repozytorium, cwd, argumentu lub zmiennej środowiskowej;
- wszystkie kontrprzykłady i klasy ataku wymagane przez ADR oraz macierz są zablokowane;
- input pozostaje niezmieniony w istotnym stanie bezpieczeństwa;
- CASE-001–003 przechodzą;
- pełne CI jest zielone dla `REVIEWED SHA`;
- nie znaleziono false success w zdefiniowanym modelu zagrożeń.

## REWORK

Gdy naprawa jest częściowa, dowody są niekompletne albo macierz nadal ujawnia wykonalny wektor.

## STOP

Gdy bezpieczne rozwiązanie wymaga zaufania do wejściowego `.git`, osłabienia sandboxu, nieweryfikowalnego pochodzenia obiektów albo nieproporcjonalnie dużej platformy względem wartości pilota.
