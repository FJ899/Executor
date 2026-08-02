# Pilot Runtime Consolidation

## Status

```text
STATUS: IMPLEMENTED IN STACKED DRAFT
PR: #27
BASE: #26 CASE-003
CONTROLLED CASES: 001, 002, 003 ONLY
AI WORKER: NOT USED
M3: NOT USED
UNIVERSAL EXTERNAL EXECUTION: NOT IMPLEMENTED
AUTO MERGE: FORBIDDEN
```

## Cel

Po trzech rzeczywistych przebiegach usunąć powielony kod bez osłabienia granic bezpieczeństwa i dowodów.

## Wynik strukturalny

Przed konsolidacją mechanika wykonawcza była powtórzona w:

- `executor/pilot_case_001.py`;
- `executor/pilot_case_002.py`;
- `executor/pilot_case_003.py`;
- `executor/sandbox/pilot.py`.

Po konsolidacji:

- `executor/pilot_core.py` zawiera wspólną mechanikę;
- trzy moduły `pilot_case_*` zawierają kontrakt, dokładny wzorzec defektu, dokładną zamianę i cienkie wrappery zgodności;
- `executor/sandbox/pilot.py` pozostaje cienkim wrapperem CASE-001.

## Pomiar

Diff względem końca CASE-003:

```text
files changed: 5
additions: 621
deletions: 942
net change: -321 lines
```

Zmiany według pliku:

```text
pilot_case_001.py: +63 / -300
pilot_case_002.py: +41 / -293
pilot_case_003.py: +40 / -276
pilot_core.py:     +472 / -0
sandbox/pilot.py:  +5 / -73
```

Redukcja nie jest uznawana za wartość sama w sobie. Jest zaakceptowana tylko dlatego, że stare testy i trzy realne przebiegi nadal przechodzą.

## Zachowane granice

Wspólny rdzeń nadal wymaga:

1. dokładnej nazwy repozytorium;
2. dokładnego commita wejściowego;
3. dokładnego bloba `PILOT_CONTRACT.md`;
4. czystego checkoutu źródłowego;
5. katalogu wyników poza źródłem;
6. osobnego worktree i brancha;
7. wyłączonych hooków oraz ograniczonej konfiguracji Git;
8. dokładnie jednego dozwolonego zmienionego pliku;
9. dokładnie jednego commita bezpośrednio na wejściu;
10. zweryfikowanego patcha;
11. read-only źródła w Dockerze;
12. braku sieci, sekretów i dostępu do HOME;
13. `compileall` i pełnych testów targetu;
14. raportu oraz statusu `ACTION_COMPLETED_REVIEW_REQUIRED`;
15. decyzji człowieka przed jakimkolwiek przyjęciem zmiany.

## Walidacja

Ostateczny kod przed dodaniem niniejszego dokumentu przeszedł workflow:

```text
run: 30765769760
foundation-tests: SUCCESS
sandbox-security: SUCCESS
CASE-001 real run: SUCCESS
CASE-002 real run: SUCCESS
CASE-003 real run: SUCCESS
source checkouts pinned and clean: SUCCESS
container cleanup: SUCCESS
```

Istniejące testy przypadków nie zostały przepisane pod refaktoryzację. Sprawdzają nowy rdzeń przez zachowane publiczne wrappery.

## Granica zaufania

`pilot_core.py` nie jest uniwersalnym API wykonywania dowolnych projektów.

Aktualny dowód obejmuje wyłącznie trzy znane kontrakty i trzy znane transformacje w `executor-pilot-target`. CLI udostępnia tylko `--case 001|002|003`. Dodanie innego repozytorium lub workera wymaga nowej jawnej decyzji oraz nowych testów.

## Werdykt

```text
DUPLICATED PILOT RUNTIME: ELIMINATED
THREE-CASE TECHNICAL BEHAVIOR: PRESERVED
CURRENT CONSOLIDATED STACK: TECHNICALLY ACCEPTABLE FOR REVIEW
PRODUCT VALUE: NOT PROVEN
FIN-008: OPEN
```

## Następna bramka

Nie należy dodawać następnego deterministycznego przypadku.

Kolejna praca ma odpowiedzieć na pytanie, czy jeden rzeczywisty worker może rozwiązać te same małe zadania bez zakodowanej z góry zamiany, przy zachowaniu wspólnego rdzenia i decyzji człowieka.

Przed tym etapem trzeba świadomie rozstrzygnąć sposób uporządkowania stacku #23, #24, #26 i #27. Nie należy scalać czterech eksperymentalnych PR-ów po kolei bez squasha lub czystego replacement PR.
