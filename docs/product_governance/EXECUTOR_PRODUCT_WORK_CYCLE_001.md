document: Executor Product Work Cycle
version: 1.0
status: EXECUTED / GOVERNANCE ROUND COMPLETE / P1 EXECUTION GATE PENDING
cycle_id: PRODUCT-WORK-CYCLE-001
date: 2026-08-03
scope: establish canonical product levels and bind active work to the P1 gate
repository: litrgratis-pixel/Executor

# Executor Product Work Cycle 001 — zamrożenie drabiny i aktywnej bramki P1

## 1. Cel rundy

Wprowadzić jedną kanoniczną definicję poziomów produktu i zastosować ją do aktualnego stanu prac, tak aby infrastruktura, bezpieczeństwo i nowe funkcje nie rozwijały się jako boczne odnogi.

Runda nie ma implementować nowej zdolności runtime. Ma ustalić, które istniejące prace są wymagane przez bieżącą bramkę produktu i jakie działanie jest następne.

## 2. Dane wejściowe

```text
CURRENT MAIN PRODUCT LEVEL:
P0 — FOUNDATION / ACHIEVED IN DECLARED SCOPE

CURRENT TARGET:
P1 — CONTROLLED PILOT RUNTIME

PR #29 CANDIDATE SHA:
3f6e4196af4b9144ceaaba08f2b6637acdc1698d

PR #29 STATUS:
DRAFT / REWORK / EXACT-SHA CI MISSING

PR #32 CANDIDATE SHA:
901e78590a446544a5d25abcecddd3e282072500

PR #32 ROLE:
O1 EXACT-REF INFRASTRUCTURE ENABLER / NOT A PRODUCT LEVEL
```

Wartości SHA są zapisem stanu przekazanego do rundy. Każda późniejsza zmiana SHA wymaga ponownego związania dowodów z nowym stanem.

## 3. Klasyfikacja według drabiny

### PR #29

```text
CURRENT PRODUCT LEVEL: P0
TARGET PRODUCT LEVEL: P1
LEVEL BLOCKER REMOVED: kontrolowany runtime pilota i evidence exact-SHA
USER-VISIBLE CAPABILITY ADDED: kontrolowana transformacja CASE-001–003 wymagająca review
REQUIRED BY CURRENT GATE: YES
PRIMARY MATURITY AXIS: T / S / O
AXIS STEP: T2 / S1 / O1
STATUS: CANDIDATE / REWORK UNTIL EXACT-SHA EVIDENCE
```

### PR #32

```text
CURRENT PRODUCT LEVEL: P0
TARGET PRODUCT LEVEL: P1
LEVEL BLOCKER REMOVED: brak powtarzalnej ścieżki ręcznego uruchomienia pełnej walidacji dla dokładnego SHA
USER-VISIBLE CAPABILITY ADDED: brak nowego poziomu produktu; umożliwia wiarygodną decyzję o P1
REQUIRED BY CURRENT GATE: YES
PRIMARY MATURITY AXIS: O
AXIS STEP: O1
STATUS: INFRASTRUCTURE ENABLER / SCOPE MUST END AFTER P1 VERIFICATION
```

## 4. Praca dopuszczona w rundzie

1. Dodać `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` jako kanoniczną definicję P0–P7.
2. Powiązać `README.md` oraz dokument celu produktu z drabiną.
3. Dodać obowiązkowy szablon PR wymagający wskazania poziomu, osi, dowodu i non-goals.
4. Dodać test governance wykrywający brak poziomów, sekcji lub odwołań.
5. Uznawać PR #32 wyłącznie jako enabler bieżącej bramki P1.
6. Po osobnym review PR #32 uruchomić exact-SHA verification dla PR #29.

## 5. Praca odroczona

Do czasu decyzji P1 `ACCEPT` nie wolno rozpoczynać:

- workera AI i P2;
- realnego pilota P3;
- M3 / T3;
- Company Loop / D2;
- panelu operatorskiego / O3;
- provider frameworka;
- wielorepozytoryjnego wykonania;
- ogólnej platformy workflow.

## 6. Wynik rundy

```text
PRODUCT LADDER:
USER APPROVED / AUTHORITATIVE PACKAGE PREPARED

ACTIVE PRODUCT GATE:
P1

PR #29:
CANDIDATE / REWORK

PR #32:
REQUIRED O1 ENABLER / REVIEW BEFORE MERGE

NEW RUNTIME WORK:
NOT AUTHORIZED IN THIS ROUND

PRODUCT LEVEL ADVANCED:
NO
```

Runda ustanawia governance, ale nie ogłasza P1. P1 może zostać osiągnięty wyłącznie po exact-SHA runie, inspekcji surowego evidence i niezależnym werdykcie `ACCEPT`.

## 7. Następne jedno działanie

```text
Przeprowadzić osobny review dokładnego workflow PR #32.
Jeżeli review zakończy się ACCEPT:
→ scalić wyłącznie PR #32;
→ uruchomić manual exact-ref verification dla SHA 3f6e4196...;
→ sprawdzić artefakt;
→ wydać ACCEPT / REWORK / STOP dla PR #29.
```

Każdy inny kierunek pozostaje poza aktywną roadmapą, dopóki nie zostanie wykazany jako mierzony blocker P1.

## 8. Ograniczenia dowodu

Ta runda nie dowodzi:

- poprawności workflow PR #32;
- zielonego runu dla PR #29;
- działania realnego acquisition i CASE-001–003 na kandydacie;
- osiągnięcia P1;
- wartości workera AI albo pełnego produktu.

Dowodzi wyłącznie, że aktywna praca została sklasyfikowana według jednej drabiny i że następna czynność jest jednoznaczna.
