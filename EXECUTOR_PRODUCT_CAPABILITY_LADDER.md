document: Executor Product Capability Ladder
version: 1.0
status: USER APPROVED / AUTHORITATIVE PRODUCT GOVERNANCE
date: 2026-08-03
scope: product capability levels, cross-cutting maturity axes, progression gates and PR alignment
repository: litrgratis-pixel/Executor

# Executor Product Capability Ladder v1.0

## 1. Cel dokumentu

Ten dokument jest kanoniczną definicją poziomów rozwoju produktu. Odpowiada na pytania:

- jaki kompletny rezultat użytkowy istnieje na danym poziomie;
- które zdolności są obowiązkowe, a które są tylko usprawnieniem osi pomocniczej;
- jakie dowody są wymagane przed ogłoszeniem kolejnego poziomu;
- czego nie wolno rozwijać przed udowodnieniem bieżącej wartości;
- jak odróżnić poziom produktu od infrastruktury, bezpieczeństwa, panelu, providera lub pojedynczej funkcji.

Dokument nie zmienia nadrzędnego celu produktu. Cel, role Ginsenga, Company Loop, Creative OS, Executora i audytu pozostają zdefiniowane w `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`.

## 2. Hierarchia dokumentów

W razie sprzeczności obowiązuje kolejność:

1. `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md` — po co istnieje produkt i kto ma jaką odpowiedzialność;
2. `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` — jakie poziomy produktu istnieją i jakie bramki je rozdzielają;
3. `CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md` — jak wykonywana i audytowana jest praca;
4. `EXECUTOR_CHARTER.md` i `EXECUTOR_POLICY.yaml` — granice zaufania oraz deterministyczne reguły runtime;
5. zaakceptowane ADR-y — lokalne decyzje implementacyjne, które nie mogą samodzielnie zmienić celu ani poziomu produktu;
6. plany postępu i PR-y dokumentacyjne — zapis bieżącego stanu, a nie źródło nowych poziomów.

Zmiana poziomów, bramek albo ich znaczenia wymaga jawnej decyzji użytkownika i nowej wersji tego dokumentu.

## 3. Zasada samochodu

Poziom produktu opisuje kompletny użyteczny „pojazd”, a nie jakość pojedynczej części.

- sandbox, provenance i M3 rozwijają oś zaufania;
- worker AI rozwija oś autonomii;
- Company Loop rozwija oś jakości decyzji;
- obsługa wielu repozytoriów rozwija oś zakresu;
- panel rozwija oś operacyjną i UX;
- optymalizacja tokenów rozwija oś efektywności.

Żadna pojedyncza oś nie tworzy automatycznie nowego poziomu produktu. Nowy poziom istnieje dopiero wtedy, gdy użytkownik otrzymuje nowy, kompletny rezultat i przechodzi jego bramka dowodowa.

## 4. Statusy poziomu

Każdy poziom ma jeden status:

- `LOCKED` — nie wolno rozpoczynać implementacji;
- `PLANNED` — poziom jest zdefiniowany, ale nie jest aktualną bramką;
- `IN_PROGRESS` — aktualny poziom docelowy;
- `CANDIDATE` — implementacja istnieje, lecz brakuje wymaganych dowodów lub review;
- `ACHIEVED` — wszystkie kryteria i dowody są spełnione dla wskazanego SHA;
- `REWORK` — kontrprzykład albo luka dowodowa blokuje uznanie poziomu;
- `STOPPED` — dalszy rozwój tego poziomu jest nieuzasadniony.

Status `ACHIEVED` zawsze musi wskazywać dokładny commit, runy, evidence i decyzję człowieka.

# 5. Pionowa drabina produktu

## P0 — FOUNDATION

### USER OUTCOME

Użytkownik nie może jeszcze produktywnie delegować zadania. Istnieją sprawdzalne podzespoły runtime.

### REQUIRED CAPABILITIES

- walidacja kontraktów testowych i projektowych;
- deterministyczna polityka;
- automat stanów i checkpointy;
- izolowany sandbox dla fixtures;
- zachowanie fail-closed w deklarowanym zakresie.

### REQUIRED EVIDENCE

- testy M0, M1, M2A i M2B;
- negatywne testy walidacji i polityki;
- rzeczywiste testy sandboxu na fixtures;
- brak fallbacku do wykonania na hoście.

### EXIT GATE

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B: IMPLEMENTED / FIXTURES VERIFIED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
```

### NON-GOALS

- worker AI;
- wykonanie realnego repozytorium;
- Company Loop;
- terminalny `PASS` pełnego produktu;
- panel operatorski.

### STOP CONDITIONS

- fundamenty wymagają ukrytego zaufania do wejścia;
- testy przechodzą mimo wyłączenia kluczowych zabezpieczeń;
- sandbox wymaga hostowego fallbacku.

## P1 — CONTROLLED PILOT RUNTIME

### USER OUTCOME

Użytkownik może uruchomić z góry określoną, ograniczoną transformację na przypiętym pilocie i otrzymać evidence wymagające review człowieka.

### REQUIRED CAPABILITIES

- kontrolowane pozyskanie dokładnego źródła;
- brak użycia nieufnego lokalnego `.git`;
- dokładnie jeden dozwolony plik i jeden commit wynikowy;
- bezpośredni rodzic równy commitowi wejściowemu;
- testy w Dockerze bez sieci workera;
- niezmienność wejścia;
- status najwyżej `ACTION_COMPLETED_REVIEW_REQUIRED`;
- exact-SHA CI i surowy artefakt evidence.

### REQUIRED EVIDENCE

- zaakceptowany PR runtime;
- realne CASE-001, CASE-002 i CASE-003;
- testy clean, smudge, process, include oraz ścieżek Git;
- process trace;
- manifesty;
- cleanup;
- artefakt związany z pełnym SHA;
- niezależne adversarial review.

### EXIT GATE

```text
REWORK SCOPE COMPLIANCE: PASS
INPUT MODEL COMPLIANCE: PASS
OBJECT IDENTITY: PASS
ORIGIN ANCHOR: PASS
GIT INPUT ISOLATION: PASS
INPUT IMMUTABILITY: PASS
CASE-001: PASS
CASE-002: PASS
CASE-003: PASS
DEFINED ADVERSARIAL SUITE: PASS
EXACT-SHA EVIDENCE: PRESENT
RAW EVIDENCE ARTIFACT: PRESENT + HASHED
FALSE SUCCESS FOUND WITHIN DEFINED THREAT MODEL: NO
FINAL DECISION: ACCEPT
```

### NON-GOALS

- AI samodzielnie rozwiązujące zadanie;
- obsługa dowolnych repozytoriów;
- M3;
- provider framework;
- panel CI;
- automatyczny merge.

### STOP CONDITIONS

- bezpieczny runtime wymaga osłabienia sandboxu;
- lokalny checkout pozostaje ukrytą ścieżką wykonania;
- exact-SHA evidence nie może zostać uzyskane w rozsądnym modelu operacyjnym.

## P2 — AI WORKER MVP

### USER OUTCOME

Użytkownik może powierzyć jednemu workerowi AI małą, wcześniej przygotowaną zmianę i otrzymać ograniczony patch do review.

### REQUIRED CAPABILITIES

- jeden jawnie wskazany provider i model;
- worker nie otrzymuje gotowej naprawy;
- worker zwraca wyłącznie propozycję zmiany;
- maksymalnie jedna automatyczna korekta po czytelnym błędzie testu;
- brak GitHub write API, push, merge, sekretów i sieci sandboxu;
- pełne prompt, model, tokeny, koszt i liczba prób w evidence;
- kontrola jednego pliku i jednego commita pozostaje aktywna.

### REQUIRED EVIDENCE

- CASE-001–003 rozwiązane przez rzeczywistego workera;
- brak ręcznej edycji rozwiązania;
- brak zmian testów i dozwolonych ścieżek;
- kompletne evidence każdego przebiegu;
- odtwarzalny wynik `ACTION_COMPLETED_REVIEW_REQUIRED`.

### EXIT GATE

```text
CASE-001: SOLVED
CASE-002: SOLVED
CASE-003: SOLVED
MANUAL CODE EDITS: 0
POLICY VIOLATIONS: 0
FALSE SUCCESS FOUND WITHIN DEFINED THREAT MODEL: NO
```

### NON-GOALS

- provider framework;
- wybór najlepszego modelu dla każdego zadania;
- Company Loop;
- realny zewnętrzny pilot wartości;
- nieograniczone retry.

### STOP CONDITIONS

- wynik 0/3;
- człowiek musi pisać rozwiązanie;
- worker wymaga osłabienia granic bezpieczeństwa;
- koszt pojedynczego prostego zadania jest nieproporcjonalny.

## P3 — REAL VALUE MVP

### USER OUTCOME

Użytkownik powierza rzeczywisty, mały problem w prawdziwym repozytorium i otrzymuje sensowną naprawę, której review wymaga mniej pracy niż ręczne wykonanie.

To jest pierwsze właściwe MVP produktu.

### REQUIRED CAPABILITIES

- kontrakt realnego zadania z dokładnym repozytorium i commitem;
- zadanie ograniczone do 1–3 plików;
- rzeczywisty kontrprzykład albo błąd;
- test regresyjny lub równoważny obserwowalny rezultat;
- draft PR bez automatycznego ready i merge;
- pomiar czasu, kosztu i udziału człowieka.

### REQUIRED EVIDENCE

- rzeczywisty problem naprawiony;
- reviewer uznał patch za sensowny;
- brak ręcznego napisania rozwiązania;
- evidence pozwala odtworzyć run;
- czas człowieka został realnie zmniejszony;
- koszt jest znany;
- `FIN-008` może osiągnąć najwyżej `PARTIAL` po jednym sukcesie.

### EXIT GATE

```text
REAL PROBLEM FIXED: YES
REGRESSION EVIDENCE: PASS
MANUAL SOLUTION EDITS: 0
HUMAN REVIEW: ACCEPTED
HUMAN TIME REDUCED: YES
RUN REPRODUCIBLE: YES
PRODUCT DECISION: CONTINUE / REWORK / STOP
```

### NON-GOALS

- szeroka refaktoryzacja;
- uniwersalna platforma;
- wiele providerów;
- pełne M3;
- panel operatorski;
- wielorepozytoryjne wykonanie.

### STOP CONDITIONS

- worker nie tworzy użytecznych patchy;
- reviewer musi przepisać większość rozwiązania;
- proces jest wolniejszy lub droższy od wykonania ręcznego;
- evidence nie ułatwia review.

## P4 — REPEATABLE EXECUTOR 1.0

### USER OUTCOME

Użytkownik może regularnie delegować jasno określoną klasę małych zadań i otrzymywać powtarzalne, uczciwe wyniki.

### REQUIRED CAPABILITIES

- jawnie zdefiniowana wspierana klasa zadań;
- co najmniej kilka realnych zadań i więcej niż jedno repozytorium albo kilka niezależnych modułów;
- bounded retry i uczciwe `BLOCKED` / `FAILED`;
- stabilny kontrakt zadania;
- powtarzalny operator workflow;
- metryki kosztu, czasu, skuteczności i udziału człowieka;
- polityka wersji modelu i regresji.

### REQUIRED EVIDENCE

- seria realnych pilotów;
- znany success rate i failure taxonomy;
- porównanie z wykonaniem ręcznym;
- stabilność po zmianie modelu lub zależności;
- udokumentowane ograniczenia produktu.

### EXIT GATE

```text
SUPPORTED TASK CLASS: FROZEN
REAL RUNS: SUFFICIENT FOR REPEATABILITY CLAIM
REVIEW ACCEPTANCE RATE: MEASURED
COST AND HUMAN TIME: MEASURED
FAILURES ARE FAIL-CLOSED: YES
EXECUTOR 1.0 DECISION: ACCEPT
```

### NON-GOALS

- dowolne zadanie programistyczne;
- dowolne repozytorium;
- samodzielna decyzja semantyczna;
- pełna integracja Creative OS;
- enterprise platform.

### STOP CONDITIONS

- brak powtarzalności;
- stale rosnąca liczba wyjątków per repozytorium;
- operator workflow jest trudniejszy niż ręczna praca;
- nowe funkcje nie poprawiają mierników użytkowych.

## P5 — DECISION-AUGMENTED EXECUTOR

### USER OUTCOME

Użytkownik może podać cel i granice bez znajomości najlepszej architektury, a system przedstawia wartościowe warianty, rekomendację i przekazuje zatwierdzony kierunek do Executora.

### REQUIRED CAPABILITIES

- minimalny Company Loop;
- rozdzielenie celu od sugerowanego rozwiązania;
- oceny co najmniej: `VALUE`, `FEASIBILITY`, `RISK`, `VERIFICATION`;
- niezależne pierwsze oceny przed syntezą;
- `PASS`, `CONCERN`, `VETO` z dowodem;
- zwięzły `POTENTIAL_AND_DECISION_PACKET`;
- decyzje semantyczne pozostają po stronie użytkownika.

### REQUIRED EVIDENCE

- eksperyment A/B: bezpośredni agent kontra Company Loop;
- jakość planu i wyniku;
- liczba przeoczonych ryzyk;
- koszt i czas;
- liczba poprawek;
- powody odrzuconych wariantów;
- brak sztucznego konsensusu jako dowodu.

### EXIT GATE

```text
MEANINGFULLY DIFFERENT OPTIONS: PRESENT
INDEPENDENT REVIEWS: PRESENT
VETO CANNOT BE SILENTLY OVERRIDDEN: YES
BOARD PACKET: USABLE
COMPANY LOOP OUTPERFORMS OR JUSTIFIES ITS COST: YES
USER SEMANTIC CONTROL: PRESERVED
```

### NON-GOALS

- wiele trwałych agentów udających pracowników;
- Board jako centrum prawdy;
- automatyczna zmiana celu;
- generowanie maksymalnej liczby pomysłów;
- wykonywanie przed decyzją użytkownika.

### STOP CONDITIONS

- Company Loop nie poprawia decyzji;
- koszt i opóźnienie przewyższają korzyść;
- role powtarzają te same argumenty;
- syntezator ukrywa weta albo niepewność.

## P6 — INTEGRATED CREATIVE OS BETA

### USER OUTCOME

Użytkownik otrzymuje ciągłość od intencji i potencjału, przez decyzję, do wykonania i oceny skutku w kilku współpracujących projektach.

### REQUIRED CAPABILITIES

- integracja Ginseng, Company Loop, Creative OS, Executor i audytu;
- kanoniczny stan i zależności między projektami;
- ocena skutków pośrednich;
- kontrolowane zadania wielorepozytoryjne albo jawny podział na sekwencyjne kontrakty;
- wykrywanie dryfu celu;
- wynik porównywany z celem użytkowym.

### REQUIRED EVIDENCE

- `GINSENG_TEST-003` albo jego formalnie zaakceptowany następca;
- niezmieniony baseline tam, gdzie jest wymagany;
- jasne rozdzielenie stanu bazowego, scenariuszy i propozycji;
- uczciwe `BLOCKED`, jeśli brakuje danych;
- review pełnego łańcucha decyzji i wykonania.

### EXIT GATE

```text
INTENTION TRACE: PASS
DEPENDENCY MAP: PASS
OPTION EXPANSION: PASS
USER DECISION: RECORDED
EXECUTION: VERIFIED
REAL EFFECT CHECK: PASS OR HONEST BLOCKED
```

### NON-GOALS

- nieograniczona autonomia;
- automatyczna zmiana kanonu;
- niekontrolowane wykonanie wielorepozytoryjne;
- deklaracja absolutnej poprawności.

### STOP CONDITIONS

- integracja niszczy lokalne źródła prawdy;
- stan globalny staje się nieaudytowalny;
- użytkownik traci kontrolę nad zmianami semantycznymi;
- system potrafi wykonać workflow, ale nie potrafi ocenić skutku.

## P7 — FULL VISION / PRODUCTION CANDIDATE

### USER OUTCOME

System może odpowiedzialnie wspierać regularną pracę nad portfelem projektów, zachowując użytkownika jako właściciela kierunku i dostarczając odtwarzalne dowody decyzji oraz wykonania.

### REQUIRED CAPABILITIES

- dojrzałe granice zaufania i niezależna weryfikacja;
- kontrolowane skalowanie modeli i repozytoriów;
- stabilny interfejs operatora;
- polityki kosztu i zasobów;
- migracje kontraktów i kompatybilność;
- monitoring dryfu, regresji i jakości decyzji;
- procedury incydentowe i rollback.

### REQUIRED EVIDENCE

- długotrwałe użycie na rzeczywistych zadaniach;
- znane klasy awarii;
- audyty bezpieczeństwa i wartości produktu;
- mierzalna oszczędność czasu albo poprawa jakości;
- utrzymanie kosztu i złożoności w przyjętych granicach.

### EXIT GATE

Zostanie zamrożona dopiero po osiągnięciu P6. Nie wolno obecnie tworzyć szczegółowej platformy P7 przez domysł.

### NON-GOALS

- absolutna autonomia;
- absolutny dowód poprawności kodu;
- zastąpienie użytkownika jako właściciela celu;
- produkt cyberbezpieczeństwa udający całe Creative OS.

### STOP CONDITIONS

- skala zwiększa false success;
- utrzymanie przewyższa wartość;
- platforma przestaje być możliwa do audytu;
- rozwój służy infrastrukturze, a nie użytkownikowi.

# 6. Poziome osie dojrzałości

Poziome osie służą do planowania funkcji. Nie zastępują poziomów P0–P7.

## T — TRUST AND EVIDENCE

- `T0`: deklaracje i kontrakty bez wykonawczego dowodu;
- `T1`: M0–M2B, sandbox i integralność na fixtures;
- `T2`: kontrolowane źródło, human gate, exact-SHA evidence i pilot runtime;
- `T3`: niezależny verifier, replay, atomowy ledger autoryzacji, action-result binding i niezależny holdout — zakres M3;
- `T4`: dojrzała atestacja, operacyjne audyty i procedury incydentowe.

M3 jest rozwojem osi `T`, a nie samodzielnym dowodem wartości produktu. Nie wolno rozpoczynać M3 przed decyzją `CONTINUE` po P3, chyba że człowiek jawnie zmieni tę bramkę z powodu potwierdzonego ryzyka.

## A — AUTONOMY

- `A0`: transformacja z góry zakodowana;
- `A1`: jeden worker AI i pojedyncza próba;
- `A2`: bounded retry bez zmiany testów i granic;
- `A3`: powtarzalna obsługa wspieranej klasy zadań;
- `A4`: kontrolowane modele lub workerzy wymienni bez zmiany bramki dowodowej.

## D — DECISION QUALITY

- `D0`: zadanie i rozwiązanie są podane bezpośrednio;
- `D1`: rozdzielenie celu od rozwiązania i kilka kandydatów;
- `D2`: minimalny Company Loop, weta i Board Packet;
- `D3`: Ginseng, Creative OS i ocena skutków w pełnym łańcuchu.

## S — SUPPORTED SCOPE

- `S0`: fixtures należące do Executora;
- `S1`: jedno allowlistowane repozytorium pilota;
- `S2`: jedno realne repozytorium wartości;
- `S3`: zdefiniowana klasa zadań i repozytoriów;
- `S4`: kontrolowane zadania wielorepozytoryjne.

## O — OPERATIONS AND UX

- `O0`: narzędzia deweloperskie i ręczne komendy;
- `O1`: exact-SHA workflow, evidence i powtarzalna bramka review;
- `O2`: stabilny operator workflow, metryki i obsługa błędów;
- `O3`: panel operatorski uzasadniony realnym użyciem;
- `O4`: operacje portfela projektów.

Panel nie może być rozwijany przed P4, chyba że ręczny operator workflow został zmierzony jako główny blocker wartości P3.

## E — EFFICIENCY

- `E0`: koszt i czas nie są mierzone;
- `E1`: tokeny, koszt, czas i próby są rejestrowane;
- `E2`: wykazana oszczędność czasu albo poprawa jakości względem baseline;
- `E3`: budżety, przewidywalność i optymalizacja;
- `E4`: skalowanie przy utrzymaniu wartości jednostkowej.

# 7. Minimalne progi osi dla poziomów

| Poziom | Trust | Autonomy | Decision | Scope | Operations | Efficiency |
|---|---:|---:|---:|---:|---:|---:|
| P0 | T1 | A0 | D0 | S0 | O0 | E0 |
| P1 | T2 | A0 | D0 | S1 | O1 | E0 |
| P2 | T2 | A1 | D0 | S1 | O1 | E1 |
| P3 | T2 | A1 | D0 | S2 | O1 | E2 |
| P4 | T2 | A3 | D0 | S3 | O2 | E2 |
| P5 | T2 | A3 | D2 | S3 | O2 | E2 |
| P6 | T3 | A3 | D3 | S4 | O2 | E2 |
| P7 | T4 | A4 | D3 | S4 | O3+ | E3+ |

Tabela określa minima. Wyższy poziom osi nie kompensuje braku rezultatu użytkowego ani innej wymaganej osi.

# 8. Aktualny stan i kolejność

```text
CURRENT MAIN PRODUCT LEVEL: P0 — FOUNDATION / ACHIEVED IN DECLARED SCOPE
P0 ACHIEVED SHA: b092a85e82eb81ec6dc7db4a7064409c6c383359
P0 EVIDENCE PR: #16
P0 EVIDENCE RUN ID: 30755381646
P0 EVIDENCE DOCUMENT: docs/M0_M2B_FINAL_ENTRY_GATE_2026-08-02.md
P0 HUMAN DECISION: ACCEPTED THROUGH MERGE OF PR #16
CURRENT TARGET: P1 — CONTROLLED PILOT RUNTIME
PR #29: P1 IMPLEMENTATION CANDIDATE / REWORK UNTIL EXACT-SHA EVIDENCE
PR #32: O1 INFRASTRUCTURE ENABLER / NOT A PRODUCT LEVEL
NEXT AFTER P1: P2 — AI WORKER MVP
FIRST TRUE PRODUCT MVP: P3 — REAL VALUE MVP
M3: T3 TRUST AXIS / LOCKED UNTIL P3 PRODUCT DECISION CONTINUE
COMPANY LOOP: D2 / TARGETED AT P5
PANEL: O3 / LOCKED UNTIL P4 OR MEASURED P3 OPERATOR BOTTLENECK
```

Obowiązująca krytyczna ścieżka:

```text
P1 exact-SHA verification
→ P1 ACCEPT / REWORK / STOP
→ jeden AI worker
→ CASE-001–003 przez workera
→ P2 gate
→ jeden realny pilot wartości
→ P3 gate i decyzja CONTINUE / REWORK / STOP
→ dopiero potem wybór kolejnego ograniczenia: repeatability, T3/M3 lub D2/Company Loop
```

Po P3 kolejna inwestycja jest wybierana na podstawie mierzonego ograniczenia, ale nie może ominąć wymagań następnego deklarowanego poziomu.

# 9. Reguła dla każdej funkcji i PR

Każdy PR musi jawnie podać:

```text
CURRENT PRODUCT LEVEL:
TARGET PRODUCT LEVEL:
LEVEL BLOCKER REMOVED:
USER-VISIBLE CAPABILITY ADDED:
REQUIRED BY CURRENT GATE: YES / NO
PRIMARY MATURITY AXIS:
AXIS STEP:
EVIDENCE ADDED:
NON-GOALS:
SCOPE EXPANSION: NONE / FORMALLY APPROVED
```

## Decyzja o dopuszczeniu pracy

- `REQUIRED BY CURRENT GATE: YES` — może wejść do aktywnej roadmapy;
- `NO, BUT MEASURED BLOCKER` — wymaga jawnej decyzji użytkownika i dowodu, że blokuje wynik;
- `NO` — trafia do backlogu lub Idea Inbox;
- brak wskazanego poziomu albo osi — `REWORK` dokumentacji PR;
- funkcja rozwijająca panel, provider framework, M3, wielorepozytoryjność lub ogólną platformę przed właściwą bramką — `STOP` albo odroczenie.

# 10. Ochrona przed boczną odnogą

Praca jest boczną odnogą, jeśli spełnia co najmniej jeden warunek:

- nie usuwa blokera bieżącego poziomu;
- nie dodaje mierzalnego rezultatu użytkowego;
- rozwija oś ponad próg potrzebny dla aktualnej bramki bez wykazanego ograniczenia;
- wymaga nowego frameworka przed pierwszym realnym użyciem;
- dodaje panel przed stabilnym operator workflow;
- dodaje provider framework przed udowodnieniem jednego workera;
- dodaje M3 przed P3 `CONTINUE`;
- rozszerza repozytoria lub klasy zadań przed powtarzalnością obecnej klasy;
- zastępuje wartość użytkową liczbą testów, agentów, dokumentów albo polityk.

Każda taka praca pozostaje hipotezą, nie aktywnym etapem.

# 11. Regresja poziomu

Osiągnięty poziom może zostać cofnięty do `REWORK`, jeżeli:

- pojawi się odtwarzalny false success w jego modelu zagrożeń;
- wymagany run lub evidence nie odpowiada deklarowanemu SHA;
- zmiana zależności unieważni dowód;
- rzeczywiste użycie obali deklarowaną wartość;
- obejście bramki zostanie wykryte po merge.

Cofnięcie poziomu nie usuwa historii osiągnięcia. Zapisuje nowy blocker i wymaga nowej decyzji.

# 12. Najbliższa bramka

Na dzień zatwierdzenia tego dokumentu jedyną aktywną bramką produktu pozostaje P1:

```text
review i ewentualny merge infrastrukturalnego exact-ref workflow
→ uruchomienie exact-SHA dla kandydata PR #29
→ inspekcja surowego evidence
→ adversarial review
→ ACCEPT / REWORK / STOP PR #29
```

PR infrastrukturalny jest zakończony, gdy odblokuje powyższą decyzję. Nie może stać się ogólną platformą workflow.
