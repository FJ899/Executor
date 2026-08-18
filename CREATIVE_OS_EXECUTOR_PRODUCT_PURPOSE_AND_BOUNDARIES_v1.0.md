---
document: "Creative OS Executor — cel produktu i granice odpowiedzialności"
version: "1.0"
status: "USER APPROVED / AUTHORITATIVE PRODUCT PURPOSE"
date: "2026-08-02"
status_reconciled: "2026-08-09"
scope: "product purpose, component roles and user-facing responsibility boundaries"
implementation_status: "DOCUMENTED / IMPLEMENTATION CLAIMS OWNED BY INVENTORY AND MAIN"
repository: "JTJ07/Executor"
---

# Creative OS Executor — cel produktu i granice odpowiedzialności v1.0

## 0. Aktualna granica autorytetu dokumentu

Ten dokument pozostaje autorytatywny dla celu produktu i odpowiedzialności komponentów.

Nie jest już źródłem prawdy dla:

- bieżącej kolejności implementacji — tę określa `docs/EXECUTOR_BUILD_ORDER.md`;
- aktualnego stanu implementacji — ten wynika z `main` i jest podsumowany w `docs/architecture/IMPLEMENTATION_INVENTORY.md`;
- poziomów maturity/proof — te definiuje `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`;
- szczegółowej semantyki Action Authorization Packet — tę definiuje późniejszy dedykowany `ACTION_AUTHORIZATION_PACKET_v1.0.md`.

Pełną regułę rozstrzygania źródeł prawdy opisuje `docs/governance/DOCUMENT_AUTHORITY.md`.

## 1. Decyzja nadrzędna

Creative OS nie ma zamykać użytkownika w literalnym brzmieniu pierwszego polecenia.
Ma pomóc mu wyjść poza ograniczenia początkowego rozwiązania, rozpoznać rzeczywisty
cel, odkryć niewidoczny potencjał, porównać wartościowe kierunki i świadomie wybrać
najlepszy z nich. Dopiero zatwierdzony kierunek może zostać przekazany do wykonania.

Executor jest podporządkowanym runtime wykonawczym tego systemu. Nie jest całym
produktem, właścicielem intencji użytkownika ani substytutem Ginsenga, Creative OS
lub warstwy deliberacyjnej.

Obowiązujący przepływ odpowiedzialności:

```text
INTENCJA UŻYTKOWNIKA
→ ODKRYCIE / ROZWAŻENIE MOŻLIWOŚCI
→ KANON / ZATWIERDZONY KIERUNEK
→ KONTRAKT
→ WYKONANIE
→ DOWÓD / WERYFIKACJA
→ DECYZJA CZŁOWIEKA
```

## 2. Problem, który rozwiązuje system

Użytkownik może poprawnie rozpoznać problem, ale podać zbyt wąskie rozwiązanie.
Może też nie znać wszystkich zależności, możliwych zastosowań, skutków pośrednich
albo wariantów o większej wartości. Literalny agent wykona wtedy polecenie sprawnie,
lecz pozostawi niewykorzystany potencjał albo zoptymalizuje niewłaściwy kierunek.

System ma temu przeciwdziałać przez:

1. oddzielenie celu od rozwiązania zasugerowanego przez użytkownika;
2. wykrycie istotnych założeń i ograniczeń początkowego ujęcia;
3. poszukiwanie rozwiązań poza pierwszą ramą, proporcjonalne do wartości i ryzyka;
4. analizę skutków bezpośrednich, pośrednich oraz zależności;
5. rozróżnienie faktów, wnioskowania, hipotez i myślenia życzeniowego;
6. przedstawienie użytkownikowi rzeczywistych rozdroży zamiast zatrzymywania go
   przy każdej odwracalnej decyzji technicznej;
7. wykonanie wybranego kierunku dopiero po ustaleniu jego znaczenia;
8. porównanie końcowego efektu z celem, a nie wyłącznie z listą wykonanych kroków.

## 3. Role komponentów

### Ginseng

Ginseng jest warstwą prowadzenia intencji i możliwości. Ma:

- utrzymywać widoczny cel oraz aktualne miejsce pracy;
- pokazywać rozwidlenia, porzucone ścieżki i nowe silne kierunki;
- wykrywać dryf użytkownika i systemu;
- symulować konsekwencje decyzji;
- ujawniać potencjał wykraczający poza początkową ramę;
- przekazywać użytkownikowi zrozumiały wybór.

### Deliberation / Company Loop

Warstwa deliberacyjna poszerza i kwestionuje warianty. Może:

- generować rozwiązania z odmiennych perspektyw;
- szukać kontrargumentów, zależności i skutków ubocznych;
- porównywać warianty według jawnych kryteriów;
- proponować mikroeksperyment, gdy dowód może rozstrzygnąć wybór;
- tworzyć rekomendację i alternatywy.

Nie jest centrum zaufania. Liczba modeli, ich zgoda ani synteza nie stanowią
samodzielnego dowodu prawdziwości i nie mogą zastąpić decyzji użytkownika.

Obowiązuje dodatkowo:

```text
AI AGREEMENT != PROOF
SYNTHESIS != AUTHORIZATION
DELIBERATION MAY NOT EXPAND THE CONTRACT
```

Szczegóły zawiera `docs/philosophy/HUMAN_AI_DELIBERATION_MODEL.md`.

### Creative OS

Creative OS jest pamięcią, konstytucją i mapą zależności. Przechowuje:

- zatwierdzone cele, decyzje i kanon;
- źródła oraz ich status;
- relacje między projektami i artefaktami;
- informacje potrzebne do wykrywania skutków zmian;
- rozróżnienie stanu bazowego, scenariuszy i propozycji.

### Executor

Executor otrzymuje zatwierdzony kontrakt i zamienia go w działanie. Ma:

- sprawdzić kontrakt zadania oraz warunki sukcesu;
- zaplanować ścieżkę wykonania w granicach kontraktu;
- wykonać pracę w dozwolonym środowisku;
- mierzyć postęp i zatrzymać bezproduktywne retry;
- zebrać dowód wykonania;
- sprawdzić obserwowalny efekt wobec kryteriów kontraktu;
- zwrócić wynik do review człowieka.

Executor nie może sam zmienić celu, kanonu, priorytetów, zakresu autoryzacji ani kryteriów sukcesu.

Obowiązuje:

```text
CAPABILITY != AUTHORITY
EXECUTION != PROOF
```

### Verifier / Audyt

Verifier i audyt pełnią inne role niż Executor i Critic.

Verifier ustala, czy obserwowalne fakty spełniają wymagania kontraktu i evidence boundary.
Audyt sprawdza okresowo lub zdarzeniowo, czy:

- produkt nadal realizuje przyjęty cel;
- rozwój nie został zdominowany przez warstwę pomocniczą;
- deklarowane funkcje są rzeczywiście osiągalne;
- testy mierzą właściwy rezultat;
- system nie nadaje sobie fałszywego sukcesu;
- nie wystąpił dryf od zaakceptowanego kierunku.

Audyt nie tworzy nowej misji produktu i nie służy do oceniania autora.

## 4. Wynik przed wykonaniem

Przed zmianą semantyczną albo wyborem istotnego kierunku system może tworzyć użytkowy
`POTENTIAL_AND_DECISION_PACKET`. Jest to logiczny kontrakt wyniku, a nie obecnie
claimowany format runtime Executora.

Pakiet powinien zawierać:

1. `actual_goal` — odtworzony rzeczywisty cel;
2. `initial_frame_limits` — ograniczenia początkowego ujęcia;
3. `untapped_potential` — nowe możliwości warte uwagi;
4. `recommended_direction` — najlepszy znany kierunek i uzasadnienie;
5. `viable_alternatives` — pełne alternatywy, nie urwane fragmenty;
6. `dependencies_and_effects` — zależności oraz skutki bezpośrednie i pośrednie;
7. `facts_inferences_hypotheses` — jawne rozdzielenie podstaw wniosku;
8. `unknowns` — luki, których nie wolno ukryć pewnym językiem;
9. `user_decisions` — wyłącznie wybory zmieniające sens, koszt, zakres lub ryzyko;
10. `next_action` — jedno kompletne dalsze działanie.

Pakiet ma pomagać użytkownikowi podjąć decyzję. Nie może być długim raportem,
który ukrywa rozdroże pod nadmiarem danych.

## 5. Wynik po wykonaniu

Po zatwierdzeniu kontraktu Executor zwraca co najmniej:

- dokładny wykonany zakres;
- rezultat użytkowy;
- dowód i ograniczenia dowodu;
- różnice względem planu;
- nierozwiązane ryzyka lub zależności;
- status wymagający prawdy, nie samooceny;
- jedno wskazanie dalszej pracy.

Techniczny wynik testu lub wewnętrzny stan `PASS` nie oznacza automatycznie:

```text
HUMAN ACCEPTED
PRODUCT ACCEPTED
MERGED
MATURITY LEVEL ACHIEVED
```

## 6. Miejsce Action Authorization Packet

`ACTION_AUTHORIZATION_PACKET_v1.0.md` jest późniejszym, dedykowanym i zamrożonym
kontraktem semantycznym terminalnej autoryzacji konkretnej consequential action.

Aktualny stan `main`:

```text
INTERNAL SUPPORTING MECHANISM
CONTRACT: FROZEN
VALIDATOR: IMPLEMENTED
POSITIVE VALIDATION RESULT: READY_FOR_ATOMIC_CONSUMPTION
ATOMIC CONSUMPTION LEDGER: NOT CLAIMED ON MAIN
ACTION-RESULT BINDING: NOT CLAIMED ON MAIN
```

AAP nie jest głównym produktem, wynikiem użytkowym, rekomendacją ani dowodem wykonania.
Nie może sam poszerzyć Task Contract ani polityki.

Posiadanie credentialu lub technicznej capability nie tworzy autoryzacji.

```text
POSSESSION OF CREDENTIAL != AUTHORITY
CAPABILITY != AUTHORITY
```

Dedykowany kontrakt AAP oraz stan kodu na `main` są źródłem prawdy dla jego szczegółowej semantyki i implementacji.

## 7. Non-goals

System nie jest projektowany jako:

- produkt cyberbezpieczeństwa;
- ogólny autonomiczny agent wykonujący dowolne zadania;
- warstwa zatwierdzania każdej drobnej czynności;
- biurokratyczna bramka blokująca odwracalne decyzje techniczne w ramach kontraktu;
- komitet agentów, który sam wykonuje i sam zatwierdza własną pracę;
- mechanizm literalnego wykonywania pierwszego rozwiązania użytkownika bez możliwości wcześniejszej deliberacji;
- generator maksymalnej liczby pomysłów bez selekcji wartości;
- właściciel kanonu, priorytetów albo semantycznego stanu projektów.

Pierwszy product slice może świadomie wspierać wąską klasę zadań developerskich.
Nie oznacza to celu budowy general-purpose autonomous coding agent.

Sandbox, polityki, integralność stanu i dowód są koniecznymi fundamentami uczciwego
wykonania. Pozostają jednak warstwą pomocniczą wobec rezultatu użytkowego.

## 8. Zasady projektowe

1. Najpierw cel i potencjał, potem rozwiązanie — w warstwach, które są właścicielem deliberacji.
2. Executor wykonuje kontrakt; nie redefiniuje celu.
3. Poszerzenie przestrzeni rozwiązań nie może automatycznie poszerzyć zakresu wykonania.
4. Różne perspektywy mają dostarczać odmienne podstawy i kontrargumenty, a nie powtarzać tę samą opinię wieloma głosami.
5. Użytkownik lub autorytatywny kontrakt decyduje o zmianach semantycznych i zakresie authority.
6. Zabezpieczenie jest uzasadnione, gdy chroni wynik albo granicę odpowiedzialności. Nie może samo stać się miernikiem wartości produktu.
7. Dowód ma odpowiadać na pytanie, czy osiągnięto zakontraktowany obserwowalny rezultat, nie tylko czy wykonano komendę.
8. Każda analiza prowadząca do pracy kończy się jasnym działaniem albo decyzją.
9. AI recommendation nie jest authorization.
10. Executor nie może być autorytatywnym verifierem własnej narracji.

## 9. Kolejność dalszej budowy

Aktualna krytyczna kolejność implementacji jest własnością:

- `docs/EXECUTOR_BUILD_ORDER.md`.

Po zaakceptowaniu PR #42 baseline brzmi:

```text
PRODUCT / BUILD BASELINE
→ DOCUMENT AUTHORITY RECONCILIATION
→ GP001 MACHINE-READABLE CONTRACT
→ FIRST VERTICAL RUNTIME SLICE
→ ADVERSARIAL GP001 TESTS
→ REAL END-TO-END RUN
→ MATURITY ASSESSMENT
```

`EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` pozostaje autorytatywny dla definicji i dowodów P0/P1/P2/P3+, ale nie jest kolejką bieżących prac implementacyjnych.

Nie wracamy do rozwijania P1, M3 ani innych osi tylko dlatego, że istnieje otwarta historyczna praca. Taka praca wraca na critical path wyłącznie wtedy, gdy usuwa zmierzony blocker bieżącego product slice albo gdy po end-to-end run wymaga tego maturity assessment.

Każdy nowy PR krytycznej ścieżki powinien wskazać:

```text
BUILD MAP TARGET:
MATURITY TARGET:
CURRENT GAP:
CHANGE:
PROOF:
NON-GOALS:
```

## 10. Ochrona kierunku

Każda przyszła funkcja powinna wskazać, który etap nadrzędnego przepływu produktu
wzmacnia. Jeżeli nie można tego wykazać, funkcja pozostaje hipotezą albo trafia poza critical path zamiast automatycznie rozszerzać roadmapę.

Audyt kierunku jest wymagany, gdy:

- warstwa bezpieczeństwa zaczyna dominować nad rezultatem użytkowym bez zmierzonego blockera;
- Executor jest opisywany jako właściciel całego ekosystemu;
- deliberation jest traktowana jako dowód prawdy;
- wynik użytkowy zostaje zastąpiony technicznym statusem;
- implementacja przyspiesza kosztem zatwierdzonego kontraktu;
- capability zaczyna być mylone z authority;
- pojawia się nowy kierunek o potencjale większym niż bieżąca roadmapa.

## 11. Status

```text
PRODUCT PURPOSE: USER APPROVED / AUTHORITATIVE FOR PURPOSE AND ROLE BOUNDARIES
BUILD BASELINE: ACCEPTED THROUGH PR #42
CURRENT HUMAN-SELECTED TARGET: P4 REPEATABLE EXECUTOR 1.0 / PHASE B CANDIDATE
CURRENT PROVEN MATURITY: P0 IN DECLARED SCOPE
ACTIVE MATURITY ADVANCEMENT CLAIM: NONE
GINSENG ROLE: DEFINED / NOT IMPLEMENTED HERE
DELIBERATION MODEL: DEFINED / RUNTIME NOT CLAIMED
CREATIVE OS ROLE: DEFINED / EXTERNAL SYSTEM
EXECUTOR ROLE: FOUNDATION IMPLEMENTATION EXISTS / GP001 END-TO-END NOT YET CLAIMED
POTENTIAL_AND_DECISION_PACKET: LOGICAL CONTRACT / NOT IMPLEMENTED
ACTION AUTHORIZATION PACKET: VALIDATOR + ATOMIC LEDGER + RESULT BINDING IMPLEMENTED CANDIDATE
GENERIC EXTERNAL PROJECT EXECUTION: FORBIDDEN
BOUNDED PILOTS: TWO NAMED REPOSITORIES / DRAFT PR ONLY / REAL EVENTS PENDING
AUTO MERGE: DISABLED
```
