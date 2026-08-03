---
document: "Creative OS Executor — cel produktu i granice odpowiedzialności"
version: "1.0"
status: "USER APPROVED / AUTHORITATIVE PRODUCT DECISION"
date: "2026-08-02"
scope: "product purpose, component roles, user-facing outcome and implementation order"
implementation_status: "DOCUMENTED / NOT IMPLEMENTED"
repository: "litrgratis-pixel/Executor"
---

# Creative OS Executor — cel produktu i granice odpowiedzialności v1.0

## 1. Decyzja nadrzędna

Creative OS nie ma zamykać użytkownika w literalnym brzmieniu pierwszego polecenia.
Ma pomóc mu wyjść poza ograniczenia początkowego rozwiązania, rozpoznać rzeczywisty
cel, odkryć niewidoczny potencjał, porównać wartościowe kierunki i świadomie wybrać
najlepszy z nich. Dopiero zatwierdzony kierunek może zostać przekazany do wykonania.

Executor jest podporządkowanym runtime wykonawczym tego systemu. Nie jest całym
produktem, właścicielem intencji użytkownika ani substytutem Ginsenga, Creative OS
lub Company Loop.

Obowiązujący przepływ produktu:

```text
INTENCJA UŻYTKOWNIKA
→ ODKRYCIE RZECZYWISTEGO CELU
→ POSZERZENIE POLA MOŻLIWOŚCI
→ WERYFIKACJA Z WIELU PERSPEKTYW
→ REKOMENDACJA I ALTERNATYWY
→ DECYZJA UŻYTKOWNIKA, JEŻELI ZMIENIA SIĘ SENS
→ ODWRACALNE WYKONANIE
→ SPRAWDZENIE RZECZYWISTEGO EFEKTU
→ JASNE DALSZE DZIAŁANIE
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

### Company Loop

Company Loop jest mechanizmem poszerzania i kwestionowania wariantów. Ma:

- generować rozwiązania z odmiennych perspektyw;
- szukać kontrargumentów, zależności i skutków ubocznych;
- porównywać warianty według jawnych kryteriów;
- proponować mikroeksperyment, gdy dowód może rozstrzygnąć wybór;
- tworzyć rekomendację i alternatywy.

Company Loop nie jest centrum zaufania. Liczba agentów, ich zgoda ani wynik Board
nie stanowią samodzielnego dowodu prawdziwości i nie mogą zastąpić decyzji
użytkownika w sprawach semantycznych.

### Creative OS

Creative OS jest pamięcią, konstytucją i mapą zależności. Przechowuje:

- zatwierdzone cele, decyzje i kanon;
- źródła oraz ich status;
- relacje między projektami i artefaktami;
- informacje potrzebne do wykrywania skutków zmian;
- rozróżnienie stanu bazowego, scenariuszy i propozycji.

### Executor

Executor otrzymuje zatwierdzony kierunek i zamienia go w działanie. Ma:

- sprawdzić kontrakt zadania oraz warunki sukcesu;
- zaplanować odwracalną ścieżkę wykonania;
- wykonać pracę w dozwolonym środowisku;
- mierzyć postęp i zatrzymać bezproduktywne retry;
- zebrać dowód wykonania;
- sprawdzić efekt wobec zatwierdzonego celu;
- zwrócić wynik oraz jedno jasne dalsze działanie.

Executor nie może sam zmienić celu, kanonu, priorytetów ani kryteriów sukcesu.

### Audyt

Audyt jest okresowym lub zdarzeniowym mechanizmem korekty. Ma sprawdzać, czy:

- produkt nadal realizuje przyjęty cel;
- rozwój nie został zdominowany przez warstwę pomocniczą;
- deklarowane funkcje są rzeczywiście osiągalne;
- testy mierzą właściwy rezultat;
- system nie nadaje sobie fałszywego `PASS`;
- nie wystąpił dryf od zaakceptowanego kierunku.

Audyt nie tworzy nowej misji produktu i nie służy do oceniania autora.

## 4. Wynik przed wykonaniem

Przed zmianą semantyczną albo wyborem istotnego kierunku system tworzy użytkowy
`POTENTIAL_AND_DECISION_PACKET`. Jest to logiczny kontrakt wyniku, a nie jeszcze
zaimplementowany format runtime.

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

Po zatwierdzeniu kierunku Executor zwraca co najmniej:

- dokładny wykonany zakres;
- rezultat użytkowy;
- dowód i ograniczenia dowodu;
- różnice względem planu;
- nierozwiązane ryzyka lub zależności;
- status wymagający prawdy, nie samooceny;
- jedno wskazanie dalszej pracy.

Status techniczny `PASS` nie jest pełnym wynikiem produktu. Musi być powiązany
z konkretnym celem, artefaktem, baseline i obserwowalnym rezultatem.

## 6. Miejsce Action Authorization Packet

`Action Authorization Packet` może w przyszłości zostać wewnętrznym kontraktem
Executora, ograniczającym skutek wykonania do dokładnie zatwierdzonej czynności.
Nie jest jednak głównym produktem, wynikiem użytkowym ani zamiennikiem eksploracji
potencjału i decyzji.

Obowiązuje status:

```text
INTERNAL SUPPORTING MECHANISM
CONTRACT NOT FROZEN
NOT IMPLEMENTED
MUST NOT DEFINE M3A / M3B / M3C BY IMPLICATION
```

Jego schema, pola, relacja do M3 i kryteria akceptacji mogą zostać określone dopiero
przy zamrażaniu kontraktu M3. Do tego czasu nazwa nie uprawnia implementera do
tworzenia mechanizmu ani zmiany terminalnych statusów.

## 7. Non-goals

System nie jest projektowany jako:

- produkt cyberbezpieczeństwa;
- kolejny ogólny agent do pisania kodu;
- warstwa zatwierdzania każdej drobnej czynności;
- biurokratyczna bramka blokująca autonomiczne decyzje techniczne;
- komitet agentów, który sam wykonuje i sam zatwierdza własną pracę;
- mechanizm literalnego wykonywania pierwszego rozwiązania użytkownika;
- generator maksymalnej liczby pomysłów bez selekcji wartości;
- właściciel kanonu, priorytetów albo semantycznego stanu projektów.

Sandbox, polityki, integralność stanu i dowód są koniecznymi fundamentami uczciwego
wykonania. Pozostają jednak warstwą pomocniczą wobec celu: odkryć wartość, pomóc
wybrać kierunek i rzeczywiście go zrealizować.

## 8. Zasady projektowe

1. Najpierw cel i potencjał, potem rozwiązanie.
2. Rozwiązanie użytkownika jest kandydatem, nie automatycznie wiążącą architekturą.
3. Poszerzenie przestrzeni rozwiązań ma być proporcjonalne do możliwej wartości,
   nie tylko do ryzyka technicznego.
4. Różne perspektywy mają dostarczać odmienne podstawy i kontrargumenty, a nie
   powtarzać tę samą opinię wieloma głosami.
5. Użytkownik decyduje o zmianach semantycznych; AI samodzielnie realizuje
   odwracalne decyzje techniczne w zatwierdzonym kierunku.
6. Zabezpieczenie jest uzasadnione, gdy chroni wynik albo granicę odpowiedzialności.
   Nie może samo stać się miernikiem wartości produktu.
7. Dowód ma odpowiadać na pytanie, czy osiągnięto cel, nie tylko czy wykonano komendę.
8. Każda analiza prowadząca do pracy kończy się jasnym działaniem albo decyzją.

## 9. Kolejność dalszej budowy

Kanoniczne poziomy produktu, minimalne progi osi i bramki zawiera `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`. Ten dokument zachowuje nadrzędny cel i role komponentów; drabina odpowiada za kolejność dojrzałości produktu.

Obowiązująca krytyczna ścieżka:

```text
P1 — kontrolowany pilot runtime i exact-SHA evidence
→ P1 ACCEPT / REWORK / STOP
→ P2 — jeden rzeczywisty worker AI na CASE-001–003
→ P3 — jeden realny pilot wartości
→ decyzja CONTINUE / REWORK / STOP
→ dopiero potem inwestycje w powtarzalność, M3 lub Company Loop według zmierzonego ograniczenia
```

M3 jest rozwojem osi zaufania i dowodu, a nie samodzielnym wynikiem użytkowym. Nie wolno rozpoczynać M3 przed pozytywną decyzją produktową po P3, chyba że użytkownik jawnie zmieni tę bramkę z powodu potwierdzonego ryzyka.

Company Loop może wejść do aktywnej roadmapy dopiero po pierwszym realnym dowodzie wartości Executora. Musi zostać oceniony przez porównanie z jednym mocnym agentem, a nie przez liczbę agentów lub raportów.

Każdy nowy PR musi wskazać bieżący i docelowy poziom produktu, usuwany blocker, rezultat widoczny dla użytkownika, rozwijaną oś oraz dowód. Infrastruktura, panel, provider framework, M3 i wielorepozytoryjność pozostają odroczone, jeżeli nie usuwają aktualnego mierzonego ograniczenia.

## 10. Ochrona kierunku

Każda przyszła funkcja powinna wskazać, który etap nadrzędnego przepływu produktu
wzmacnia. Jeżeli nie można tego wykazać, funkcja pozostaje hipotezą albo trafia do
Idea Inbox, zamiast automatycznie rozszerzać roadmapę.

Audyt kierunku jest wymagany, gdy:

- warstwa bezpieczeństwa zaczyna dominować nad odkrywaniem wartości;
- Executor jest opisywany jako cały produkt;
- Company Loop jest traktowany jako dowód prawdy;
- wynik użytkowy zostaje zastąpiony technicznym statusem;
- implementacja przyspiesza kosztem zatwierdzonego celu;
- pojawia się nowy kierunek o potencjale większym niż bieżąca roadmapa.

## 11. Status

```text
PRODUCT PURPOSE: USER APPROVED / DOCUMENTED
GINSENG ROLE: DEFINED / NOT IMPLEMENTED HERE
COMPANY LOOP ROLE: DEFINED / NOT IMPLEMENTED
CREATIVE OS ROLE: DEFINED / EXTERNAL SYSTEM
EXECUTOR ROLE: FOUNDATION IMPLEMENTATION IN PROGRESS
POTENTIAL_AND_DECISION_PACKET: LOGICAL CONTRACT / NOT IMPLEMENTED
ACTION AUTHORIZATION PACKET: INTERNAL IDEA / CONTRACT NOT FROZEN / NOT IMPLEMENTED
M3+: LOCKED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
```
