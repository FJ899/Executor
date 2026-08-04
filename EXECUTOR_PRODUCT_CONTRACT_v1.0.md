---
document: "Executor Product Contract"
version: "1.0"
status: "USER APPROVED / AUTHORITATIVE EXECUTOR PRODUCT CONTRACT"
date: "2026-08-04"
scope: "controlled repository change execution, P3 input/flow/output contract, terminal statuses and MVP proof"
repository: "litrgratis-pixel/Executor"
---

# EXECUTOR — PRODUCT CONTRACT v1.0

## 1. Cel produktu

Executor jest systemem kontrolowanego wykonania zmian w repozytorium.

Nie jest:

- systemem wyboru celu;
- systemem strategicznym;
- systemem akceptacji;
- autonomicznym właścicielem projektu.

Jego odpowiedzialność:

> Wykonać zatwierdzone zadanie w określonych granicach, udowodnić przebieg i zwrócić wynik wymagający decyzji człowieka.

## 2. Relacja do pozostałych dokumentów

Ten dokument jest kanonicznym kontraktem Executora jako produktu wykonawczego oraz docelowym kontraktem P3.

- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md` zachowuje opis szerszego ekosystemu, ról Creative OS, Ginsenga i Company Loop. Nie rozszerza przez to odpowiedzialności Executora.
- `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md` zachowuje kolejność P0–P7 oraz bramki dojrzewania. P3 musi spełniać niniejszy kontrakt.
- `CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md` opisuje sposób prowadzenia i audytu pracy. Nie może zmienić wejścia, wyjścia ani granicy decyzji człowieka.
- `EXECUTOR_CHARTER.md`, `EXECUTOR_POLICY.yaml` i zaakceptowane ADR-y realizują granice techniczne. Nie mogą samodzielnie rozszerzyć celu produktu.

W razie sprzeczności dotyczącej zakresu Executora, jego wejścia, przepływu, wyjścia, statusów lub Definition of Done P3 obowiązuje niniejszy dokument jako nowsza jawna decyzja użytkownika.

## 3. Input Contract

Executor przyjmuje wyłącznie kompletny kontrakt wejściowy.

### Repository

- URL lub jednoznaczny identyfikator repozytorium;
- dokładny commit SHA;
- branch albo jawnie określony stan wejściowy.

### Task Contract

- problem;
- oczekiwany rezultat;
- kryteria akceptacji;
- dozwolony zakres zmiany.

### Policy

- dozwolone działania;
- zakazane działania;
- ograniczenia bezpieczeństwa.

### Execution Rules

- dozwolone komendy;
- obowiązkowe testy;
- limit prób;
- maksymalny zakres zmian.

Brak któregokolwiek wymaganego elementu oznacza:

```text
BLOCKED
```

Executor nie próbuje domyślać brakującego celu, zakresu, kryterium akceptacji, polityki ani autoryzacji.

## 4. Executor Flow

Jedyny obowiązujący przepływ P3:

```text
INPUT
  |
  v
Input Validation
  |
  v
Problem Analysis
  |
  v
Controlled Change
  |
  v
Repository Tests
  |
  v
Regression Tests
  |
  v
Evidence Collection
  |
  v
Draft PR
  |
  v
Status
```

Na tym kończy się granica Executora.

```text
EXECUTOR BOUNDARY
-----------------
HUMAN REVIEW
  |
  v
HUMAN DECISION
```

Human Review i Human Decision należą do pełnej architektury procesu, lecz nie są wykonywane przez Executora.

## 5. Output Contract

Executor zwraca trzy elementy.

### Draft PR

Zawiera:

- zmianę;
- opis problemu i rozwiązania;
- dokładny zakres;
- wyniki testów;
- jawne ograniczenia twierdzenia.

Draft PR nie jest automatycznie oznaczany jako ready i nie jest automatycznie scalany.

### Evidence Package

Zawiera co najmniej:

- źródło wejściowe;
- commit bazowy;
- kontrakt zadania i jego identyfikator;
- wykonane działania;
- wyniki testów;
- logi;
- wynikowy patch albo commit;
- ograniczenia dowodu;
- przyczyny ewentualnych blokad lub porażki;
- dane potrzebne do odtworzenia przebiegu.

Autorytatywne evidence musi być zebrane albo zapieczętowane poza kontrolą wykonawcy zadania.

Deklaracje wykonawcy, jego własne logi, kandydackie raporty i zgłoszony przez niego `PASS` są wyłącznie obserwacyjne. Nie mogą samodzielnie stanowić podstawy autorytatywnego wyniku.

Brak możliwości niezależnego udowodnienia wyniku oznacza:

```text
BLOCKED
```

### Status

Executor może zwrócić wyłącznie jeden z trzech statusów.

#### ACTION_COMPLETED_REVIEW_REQUIRED

Executor wykonał zakontraktowaną akcję i dostarczył wymagany materiał do review. Nie podjął decyzji o akceptacji produktu ani o merge.

#### BLOCKED

Executor nie może kontynuować zgodnie z kontraktem, polityką lub wymaganiami dowodowymi.

Przykłady:

- brak wymaganych danych;
- konflikt zasad;
- przekroczony zakres;
- brak wymaganej autoryzacji;
- brak możliwości niezależnego udowodnienia wyniku.

#### FAILED

Executor podjął dozwoloną próbę wykonania zadania, ale nie osiągnął zakontraktowanego rezultatu w granicach prób i zakresu.

## 6. Świadomie zabronione wyniki

Executor nigdy nie zwraca jako własnego wyniku:

```text
MERGED
ACCEPTED
PRODUCT PASS
```

Executor nie może być jednocześnie:

- wykonawcą;
- autorytatywnym recenzentem własnej pracy;
- właścicielem decyzji produktowej.

Techniczny wynik testu `PASS` może występować wewnątrz evidence jako wynik konkretnego testu. Nie jest terminalnym statusem Executora ani decyzją o przyjęciu zmiany.

## 7. Definition of Done — P3 MVP

Executor osiąga P3 dopiero po spełnieniu wszystkich poniższych warunków.

### Warunek 1 — rzeczywiste zadanie

Executor wykonuje nierozwiązane zadanie przynoszące wartość poza testowaniem Executora.

Nie kwalifikują się samodzielnie:

- fixture;
- benchmark;
- sztuczny przypadek;
- naprawa istniejąca już na commitcie bazowym;
- demonstracja przygotowana wyłącznie pod oczekiwane zachowanie systemu.

### Warunek 2 — rozwiązanie nie jest napisane ręcznie

Człowiek może:

- określić problem;
- ustalić granice;
- dostarczyć kontrprzykład;
- zatwierdzić albo odrzucić wynik.

Człowiek nie może napisać rozwiązania za Executora ani poprawić większości patcha przed review.

### Warunek 3 — zmiana przechodzi wymagane testy

Minimum:

```text
REQUIRED TESTS: PASS
REGRESSION TESTS OR EQUIVALENT OBSERVABLE RESULT: PASS
```

Testy muszą odpowiadać kryteriom akceptacji i nie mogą zostać osłabione przez wykonawcę.

### Warunek 4 — evidence jest odtwarzalne

Inna osoba musi móc sprawdzić:

- skąd pochodziło wejście;
- jaki commit był bazą;
- co zostało wykonane;
- jaki patch powstał;
- jakie testy uruchomiono;
- jakie były ograniczenia;
- dlaczego wynik uznano za technicznie gotowy do review.

### Warunek 5 — review jest tańsze niż wykonanie ręczne

To jest główny warunek produktowy.

Pytanie P3 nie brzmi wyłącznie:

```text
Czy zmiana działa?
```

Pytanie brzmi:

```text
Czy człowiek szybciej i bezpieczniej dochodzi do użytecznego wyniku dzięki Executorowi niż przez ręczne wykonanie zadania?
```

Należy zmierzyć co najmniej:

- czas pracy człowieka przy przygotowaniu kontraktu;
- czas review;
- koszt wykonania;
- liczbę prób;
- udział ręcznej edycji rozwiązania;
- porównawczy szacunek albo pomiar wykonania ręcznego.

## 8. Zakres P3

P3 obejmuje tylko minimalny pionowy przepływ:

```text
repo + commit + kompletny Task Contract + Policy + Execution Rules
-> kontrolowana analiza i zmiana
-> wymagane testy
-> niezależnie zapieczętowane evidence
-> draft PR
-> ACTION_COMPLETED_REVIEW_REQUIRED / BLOCKED / FAILED
-> decyzja człowieka
```

## 9. Co zostaje poza zakresem P3

Świadomie odkładamy:

- Company Loop;
- Ginseng;
- wielu agentów;
- automatyczny merge;
- wielorepozytoryjność;
- panel użytkownika;
- pełną autonomię;
- ogólny provider framework;
- rozwój funkcji, które nie usuwają blokera P1, P2 albo P3.

Brak tych elementów nie blokuje P3.

## 10. Architektura odpowiedzialności

```text
                 USER
                  |
        określa cel i ograniczenia
                  |
                  v
          Creative OS
     kontekst / decyzje / stan
                  |
                  v
           Task Contract
                  |
                  v
             EXECUTOR
             wykonanie
                  |
                  v
     Draft PR + Evidence + Status
                  |
                  v
              HUMAN
          review / decision
```

Creative OS może przechowywać kontekst, zatwierdzone decyzje i stan. Executor otrzymuje już zatwierdzony kontrakt wykonawczy i nie przejmuje roli systemu strategicznego.

## 11. Filtr każdej nowej funkcji

Od zatwierdzenia tego kontraktu każde nowe żądanie rozwoju Executora musi odpowiedzieć na pytanie:

```text
Czy ta funkcja jest konieczna, aby Executor przeszedł aktualną bramkę na drodze do P3?
```

- `NIE` — odkładamy do backlogu albo Idea Inbox;
- `TAK` — wskazujemy dokładne miejsce w przepływie, usuwany blocker i wymagany dowód;
- `NIE WIADOMO` — najpierw zbieramy dowód mierzonego ograniczenia, bez implementacji przez domysł.

## 12. P3 Pilot Contract

Pierwszy pilot P3 musi zawierać:

```text
REAL USER PROBLEM
+ REPRODUCIBLE BASELINE FAILURE OR OBSERVABLE DEFECT
+ EXTERNAL REAL REPOSITORY
+ EXACT COMMIT SHA
+ COMPLETE INPUT CONTRACT
+ BOUNDED CHANGE
+ OBJECTIVE ACCEPTANCE CRITERIA
+ INDEPENDENT EVIDENCE PATH
+ MEASURABLE MANUAL COST
```

Dodatkowe warunki:

- repozytorium nie może być `executor-pilot-target`;
- problem nie może być już naprawiony na bazowym SHA;
- człowiek nie może dostarczyć gotowego rozwiązania;
- zadanie musi przynosić wartość poza testowaniem Executora;
- wynik pozostaje draft PR wymagającym jawnej decyzji człowieka.

Status wyboru pilota na dzień zamrożenia kontraktu:

```text
P3 PILOT CONTRACT-001: NOT SELECTED
REASON: NO CURRENT COMPLETE REAL TASK CONTRACT
```

Nie należy tworzyć wygodnego benchmarku i nazywać go P3. Pierwsza nowa, odtwarzalna i nierozwiązana porażka spełniająca powyższe warunki może zostać kandydatem na `P3 PILOT CONTRACT-001`.

## 13. Kolejność dojścia do P3

Kontrakt P3 jest zamrożony, lecz nie pozwala ominąć wcześniejszych bramek.

```text
P1 — controlled pilot runtime + independent exact-SHA evidence
-> P1 ACCEPT / REWORK / STOP
-> P2 — one real AI worker, no manual solution edits
-> P2 ACCEPT / REWORK / STOP
-> P3 PILOT CONTRACT-001
-> real execution
-> ACTION_COMPLETED_REVIEW_REQUIRED / BLOCKED / FAILED
-> HUMAN ACCEPT / REWORK / STOP
```

## 14. Status kanoniczny

```text
EXECUTOR PRODUCT CONTRACT: USER APPROVED / FROZEN v1.0
CURRENT MAIN PRODUCT LEVEL: P0 — FOUNDATION
CURRENT TARGET: P1 — CONTROLLED PILOT RUNTIME
FIRST TRUE PRODUCT MVP: P3 — REAL VALUE MVP
P3 PILOT CONTRACT-001: NOT SELECTED
AUTO MERGE: FORBIDDEN
EXECUTOR SELF-ACCEPTANCE: FORBIDDEN
```
