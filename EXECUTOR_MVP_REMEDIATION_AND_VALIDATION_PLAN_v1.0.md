# Executor MVP Remediation and Validation Plan v1.0

## Status dokumentu

```text
STATUS: PROPOSED REPAIR BASELINE
RUNTIME ENFORCEMENT: NOT IMPLEMENTED
TARGET RELEASE: EXECUTOR 1.0
OWNER MODEL: SENIOR DEVELOPER + IMPLEMENTER
```

Ten dokument zamienia audyt ryzyka „projektu nieskończonego” w skończony plan naprawczy. Ma być używany przez senior developera do prowadzenia nowego pracownika przez małe, domykane etapy. Nie jest dowodem implementacji żadnego etapu.

Dokument jest jednocześnie:

- bazową listą problemów, które muszą zostać usunięte;
- kolejnością projektów naprawczych;
- planem testów dla każdego projektu;
- zestawem bramek `CONTINUE / STOP`;
- kryterium, po którym można uczciwie nazwać system wersją 1.0.

---

# 1. Jedno zdanie definiujące wersję 1.0

> **Executor 1.0 przyjmuje zatwierdzone zadanie dotyczące jednego repozytorium, tworzy bezpieczną zmianę na osobnej gałęzi, uruchamia określone testy i zwraca użytkownikowi diff oraz dowody potrzebne do decyzji o przyjęciu zmiany.**

Każda praca, która nie jest konieczna do osiągnięcia tego zdania, jest poza krytyczną ścieżką wersji 1.0.

---

# 2. Kanoniczny use case wersji 1.0

Executor 1.0 ma domknąć dokładnie jeden przypadek:

> **Napraw mały, jednoznaczny błąd posiadający istniejący deterministyczny test w przypiętym repozytorium pilotażowym; zmień wyłącznie dozwolone pliki, uruchom wskazane testy, utwórz osobną gałąź i zwróć diff, logi oraz status bez scalania.**

Nie rozszerzamy tego use case’u w trakcie budowy 1.0.

## Wynik użyteczny dla człowieka

Po jednym poleceniu operator otrzymuje:

1. identyfikator wejściowego repozytorium i commita;
2. identyfikator utworzonej gałęzi lub worktree;
3. zmienione pliki i pełny diff;
4. wykonane komendy;
5. wyniki testów;
6. jednoznaczny status;
7. informację o wszystkich ręcznych interwencjach;
8. decyzję pozostawioną człowiekowi: zaakceptować, odrzucić albo poprawić.

## Statusy wystarczające dla 1.0

```text
ACTION_COMPLETED_REVIEW_REQUIRED
NO_CHANGE_PRODUCED
TESTS_FAILED
POLICY_BLOCKED
EXECUTION_FAILED
```

Terminalny, kryptograficznie certyfikowany `PASS` nie jest wymaganiem wersji 1.0.

---

# 3. Rejestr ryzyk bazowych

Statusy dopuszczalne:

- `OPEN` — problem nadal istnieje;
- `PARTIAL` — istnieje część rozwiązania, ale brak dowodu wartości końcowej;
- `ELIMINATED` — spełniono kryterium i istnieje wskazany dowód w repo;
- `REGRESSED` — problem wcześniej zamknięty powrócił.

Nie wolno oznaczyć ryzyka jako `ELIMINATED` wyłącznie na podstawie dokumentu, klasy, interfejsu, fixture albo self-testu, który sam tworzy warunki własnego sukcesu.

| ID | Problem bazowy | Stan bazowy | Problem uznaje się za wyeliminowany dopiero, gdy istnieje |
|---|---|---:|---|
| `FIN-001` | Brak ostrego MVP | `OPEN` | zatwierdzona definicja 1.0, zamknięta lista wymagań, test release acceptance i brak obowiązkowych funkcji poza nią |
| `FIN-002` | Brak jednego domkniętego use case’u | `OPEN` | realny przepływ: task → zmiana → test → diff → decyzja człowieka, wykonany na przypiętym repo pilotażowym |
| `FIN-003` | Architektura wyprzedzająca realne potrzeby | `OPEN` | każda obowiązkowa część ścieżki 1.0 jest używana przez kanoniczny use case albo usunięta z krytycznej ścieżki |
| `FIN-004` | Zbyt wczesne abstrahowanie | `OPEN` | nie ma interfejsu lub protokołu bez aktualnego konsumenta; drugi adapter powstaje dopiero po drugim realnym przypadku |
| `FIN-005` | Budowanie platformy zamiast rozwiązania | `OPEN` | 1.0 obsługuje jeden typ działania, jeden model wykonania i jeden zamknięty wynik użytkowy |
| `FIN-006` | Roadmapa bez kryterium zakończenia | `OPEN` | każdy etap ma warunek wyjścia, limit czasu i decyzję `CONTINUE / STOP`; 1.0 nie wymaga następnego milestone’u |
| `FIN-007` | Rozproszenie na wiele kierunków | `OPEN` | Ginseng, Company Loop, GUI, multi-agent, auto-merge i uniwersalna platforma zewnętrznych projektów nie są częścią zakresu 1.0 |
| `FIN-008` | Brak dowodów użycia lub walidacji | `OPEN` | co najmniej trzy próby pilotażowe, z pomiarem pracy człowieka, poprawności wyniku i liczby interwencji |

## Zasada aktualizacji rejestru

Każdy PR, który twierdzi, że zmniejsza jedno z powyższych ryzyk, musi w opisie wskazać:

```text
RISK ID:
CO ZMIENIONO:
DOWÓD W KODZIE:
DOWÓD W TEŚCIE:
DOWÓD UŻYCIA:
NOWY STATUS: OPEN / PARTIAL / ELIMINATED / REGRESSED
```

Sam checkbox bez ścieżki do testu lub raportu nie jest dowodem.

---

# 4. Zasady pracy senior developer → nowy pracownik

## 4.1. Jeden etap, jeden wynik

Nowy pracownik nie dostaje zadania „zbuduj platformę”. Dostaje mały pionowy fragment, który kończy się obserwowalnym wynikiem.

Każdy etap przebiega tak samo:

1. senior wyjaśnia wynik dla użytkownika i trzy najważniejsze tryby awarii;
2. implementer zapisuje failing acceptance test albo powtarzalną procedurę testową;
3. implementer wprowadza najmniejszą zmianę pozwalającą test zaliczyć;
4. senior wykonuje adversarial review ścieżki pozytywnej i negatywnej;
5. implementer upraszcza kod i usuwa elementy nieużywane przez etap;
6. PR dokumentuje dowód, nie deklarację;
7. etap kończy się decyzją `CONTINUE` albo `STOP`.

## 4.2. Zakaz abstrakcji bez konsumenta

Nowy interfejs, adapter, format pakietu, magazyn lub warstwa polityki może powstać tylko wtedy, gdy:

- jest używana przez aktualny pionowy przepływ;
- usuwa konkretną duplikację albo tryb awarii;
- posiada test pokazujący ten problem przed zmianą;
- nie istnieje prostsze rozwiązanie lokalne.

„Przyda się później” nie jest kryterium akceptacji.

## 4.3. Test najpierw pokazuje wartość, potem odporność

Kolejność testów jest obowiązkowa:

1. czy użytkownik otrzymuje potrzebny wynik;
2. czy wynik jest poprawny;
3. czy nie naruszono granic;
4. czy awaria jest jawna;
5. czy wykonanie można odtworzyć w zakresie potrzebnym do review.

Nie wolno inwestować w coraz silniejszą integralność wyniku, którego nikt jeszcze nie użył.

## 4.4. Małe PR-y

Każdy PR powinien:

- realizować jeden etap lub jedną bramkę;
- wprowadzać najwyżej jeden nowy koncept architektoniczny;
- zawierać test pozytywny i przynajmniej jeden test negatywny;
- nie mieszać refaktoryzacji z nową funkcją, chyba że refaktoryzacja jest niezbędna do testu;
- pozostać draftem do czasu przedstawienia dowodu wymaganej bramki.

---

# 5. Zamrożenie zakresu przed naprawą

Do czasu ukończenia Projektu 4 obowiązuje zamrożenie:

## Nie rozwijamy na krytycznej ścieżce 1.0

- Ginsenga;
- Company Loop;
- GUI;
- wielu agentów i departamentów;
- wielu dostawców modeli;
- auto-merge;
- pracy ciągłej;
- uniwersalnego hostingu wielu projektów;
- własnego systemu metryk biznesowych;
- kolejnych formatów dowodów;
- nowych poziomów terminalnego `PASS`;
- autonomicznego wykonywania działań innych niż zmiana w repozytorium.

## Status draftów M3

Drafty M3, w tym stos PR #17–#21, pozostają eksperymentem poza krytyczną ścieżką 1.0.

Do zakończenia Projektu 4:

- nie są wymagane do wersji 1.0;
- nie powinny być rozszerzane o kolejne granice zaufania;
- nie powinny być scalane wyłącznie dlatego, że są kolejnym milestone’em;
- mogą zostać wykorzystane później tylko po wykazaniu konkretnego ryzyka z realnego pilota.

---

# 6. Plan projektów naprawczych

## Projekt 0 — Kontrakt końca i repozytorium pilotażowe

### Cel

Usunąć niejasność: co budujemy, dla kogo, kiedy kończymy i na czym to udowadniamy.

### Czas maksymalny

1–2 dni robocze.

### Zakres zmian

1. Zatwierdzić jedno zdanie wersji 1.0 z sekcji 1.
2. Zatwierdzić kanoniczny use case z sekcji 2.
3. Wskazać jedno repozytorium pilotażowe oraz przypięty commit bazowy.
4. Przygotować trzy małe błędy pilotażowe tego samego typu:
   - mają istniejący test, który przed naprawą nie przechodzi;
   - mają jednoznaczny oczekiwany wynik;
   - nie wymagają sieci ani sekretów w sandboxie;
   - mogą być naprawione w małym limicie diffu;
   - nie dotyczą bezpieczeństwa, produkcji ani danych użytkowników.
5. Zapisać limit zakresu 1.0 jako listę zamkniętą.
6. Zdefiniować raport pilotażowy i metryki wartości.

### Czego implementer ma się nauczyć

- rozróżniać wymaganie produktu od pomysłu architektonicznego;
- pisać mierzalną Definition of Done;
- projektować zadanie, które można jednoznacznie zaliczyć lub odrzucić;
- odróżniać test fixture od dowodu użycia.

### Testy Projektu 0

#### `P0-T01 — Scope consistency`

README, dokument celu produktu i ten plan nie mogą zawierać sprzecznych definicji wersji 1.0.

#### `P0-T02 — Closed use case review`

Osoba niezwiązana z implementacją potrafi na podstawie dokumentu odpowiedzieć:

- jakie jest wejście;
- jaki jest wynik;
- czego system nie robi;
- po czym poznajemy sukces;
- kiedy projekt należy zatrzymać.

#### `P0-T03 — Pilot determinism`

Każdy z trzech błędów pilotażowych:

- powtarzalnie daje czerwony test na commicie bazowym;
- ma znany oczekiwany wynik;
- nie wymaga uznaniowej oceny modelu.

### Bramka wyjścia

`CONTINUE`, tylko gdy istnieją trzy konkretne zadania pilotażowe i jeden zatwierdzony wynik 1.0.

`STOP`, gdy zespół nadal chce równocześnie budować uniwersalną platformę, Ginsenga, Company Loop i zaawansowaną attestację przed pierwszym wykonaniem.

### Powiązane ryzyka

`FIN-001`, `FIN-002`, `FIN-005`, `FIN-006`, `FIN-007`.

---

## Projekt 1 — Minimalny pionowy przepływ na fixture

### Cel

Jedno polecenie CLI ma przeprowadzić cały przepływ na repo fixture:

```text
validate → create isolated worktree/branch → invoke deterministic worker → run tests in sandbox → collect diff/logs → return status
```

Worker w tym etapie jest deterministycznym komponentem testowym. Nie udaje modelu AI. Służy do udowodnienia, że wszystkie elementy są rzeczywiście połączone.

### Czas maksymalny

3–5 dni roboczych.

### Zakres zmian

1. Dodać jedno polecenie CLI, roboczo `execute-task`.
2. Połączyć istniejące walidatory, politykę, repo identity i sandbox w jeden orchestrator.
3. Utworzyć izolowany worktree lub gałąź wynikową.
4. Dopuścić dokładnie jeden typ działania: edycję dozwolonych plików repozytorium.
5. Dodać deterministyczny worker fixture, który wykonuje małą znaną zmianę.
6. Zwrócić jeden raport wykonania, zawierający minimum:
   - repo i commit wejściowy;
   - task ID;
   - zmienione pliki;
   - diff;
   - komendy;
   - kod wyjścia testów;
   - status;
   - interwencje człowieka.
7. Nie dodawać nowego evidence store, ledgeru ani holdoutu.

### Czego implementer ma się nauczyć

- budować vertical slice zamiast zestawu niezależnych komponentów;
- używać istniejących mechanizmów bez tworzenia drugiej wersji tych samych pojęć;
- projektować jawne błędy i cleanup;
- odróżniać integrację od testu jednostkowego.

### Testy Projektu 1

#### `P1-T01 — Happy path end-to-end`

Jedno polecenie tworzy dozwoloną zmianę, uruchamia testy i zwraca `ACTION_COMPLETED_REVIEW_REQUIRED`.

#### `P1-T02 — Wrong repository commit`

Nieprawidłowy commit wejściowy blokuje run przed utworzeniem zmiany.

#### `P1-T03 — Forbidden path`

Worker próbujący zmienić plik spoza allowlisty kończy się `POLICY_BLOCKED`; niedozwolony plik pozostaje niezmieniony.

#### `P1-T04 — Test failure`

Zmiana, która nie naprawia testu, zwraca `TESTS_FAILED`, zachowuje diff do review i nie udaje sukcesu.

#### `P1-T05 — Worker crash`

Awaria workera zwraca `EXECUTION_FAILED`, nie pozostawia aktywnego procesu ani nieoznaczonego runu.

#### `P1-T06 — Sandbox timeout`

Przekroczenie czasu kończy proces, wykonuje cleanup i zachowuje jawny wynik timeoutu.

#### `P1-T07 — No host fallback`

Niedostępny Docker powoduje fail-closed, bez wykonania komend na hoście.

#### `P1-T08 — Dirty source protection`

Nieoczekiwany stan źródła nie może zostać cicho włączony do wyniku.

#### `P1-T09 — Report completeness`

Raport zawiera wszystkie pola potrzebne człowiekowi do review bez przeglądania pamięci procesu.

#### `P1-T10 — Cleanup and repeatability`

Ten sam fixture można uruchomić trzy razy bez kolizji gałęzi, katalogów, locków i kontenerów.

### Bramka wyjścia

`CONTINUE`, tylko gdy wszystkie testy `P1-*` przechodzą jednym poleceniem CI i pionowy przepływ nie wymaga ręcznego łączenia komponentów.

`STOP`, gdy do prostego fixture potrzebna jest nowa platforma pakietów, nowy magazyn dowodów albo kolejny ogólny framework.

### Powiązane ryzyka

`FIN-002`, `FIN-003`, `FIN-004`, `FIN-005`.

---

## Projekt 2 — Jeden rzeczywisty worker

### Cel

Zastąpić deterministyczny worker jednym rzeczywistym wykonawcą zdolnym przygotować zmianę kodu.

Model lub coding agent może działać poza sandboxem testowym. Sekrety i sieć nie są przekazywane do kodu badanego repozytorium ani do kontenera wykonującego testy.

### Czas maksymalny

3–5 dni roboczych.

### Warunek rozpoczęcia

Projekt 1 musi być ukończony. Nie rozpoczynamy go na zestawie niepołączonych komponentów.

### Zakres zmian

1. Wybrać jednego konkretnego wykonawcę dostępnego w środowisku projektu.
2. Dodać tylko jeden adapter lub jedno wywołanie procesu.
3. Zapisać wejście przekazane workerowi oraz jego surowy wynik.
4. Ograniczyć workerowi:
   - repo i commit;
   - dozwolone ścieżki;
   - maksymalny rozmiar zmiany;
   - maksymalną liczbę prób;
   - dozwolone komendy;
   - brak możliwości merge.
5. Zastosować zmianę wyłącznie w izolowanym worktree.
6. Nie tworzyć frameworka wielu providerów.

### Czego implementer ma się nauczyć

- izolować niedeterministyczny komponent od deterministycznej walidacji;
- logować granice wejścia i wyjścia;
- projektować retry bez ukrywania pierwszej porażki;
- nie mylić etykiety `AI_AGENT` z rzeczywistym wywołaniem agenta.

### Testy Projektu 2

#### `P2-T01 — Real worker produces patch`

Rzeczywisty worker otrzymuje fixture i tworzy patch możliwy do zastosowania.

#### `P2-T02 — Empty result`

Brak zmiany zwraca `NO_CHANGE_PRODUCED`, a nie sukces.

#### `P2-T03 — Malformed result`

Nieczytelny lub nieaplikowalny patch kończy się `EXECUTION_FAILED` z zachowanym surowym wynikiem.

#### `P2-T04 — Out-of-scope modification`

Każda próba zmiany niedozwolonej ścieżki jest odrzucana przed testami.

#### `P2-T05 — Oversized patch`

Zmiana przekraczająca limit jest blokowana i raportowana.

#### `P2-T06 — Worker unavailable`

Brak połączenia, limit usługi albo błąd procesu nie prowadzi do częściowego sukcesu.

#### `P2-T07 — Retry visibility`

Każda próba ma osobny zapis wejścia, wyjścia i przyczyny ponowienia.

#### `P2-T08 — Deterministic verification`

Status końcowy zależy od polityki i testów, nie od deklaracji workera, że zadanie zakończyło się sukcesem.

#### `P2-T09 — Fixture repetition`

Na trzech powtórzeniach tego samego fixture co najmniej dwa kończą się poprawnym wynikiem bez ręcznej edycji patcha.

### Bramka wyjścia

`CONTINUE`, gdy realny worker dwukrotnie poprawnie domyka fixture i żaden jego komunikat nie może sam nadać statusu sukcesu.

`STOP`, gdy większość pracy nadal wykonuje człowiek, a system tylko zapisuje rozbudowane pakiety wokół ręcznej zmiany.

### Powiązane ryzyka

`FIN-002`, `FIN-003`, `FIN-004`, `FIN-008`.

---

## Projekt 3 — Pilot na realnym repozytorium

### Cel

Wykonać kanoniczny use case na trzech rzeczywistych zadaniach tego samego typu w jednym przypiętym repozytorium pilotażowym.

### Czas maksymalny

5 dni roboczych.

### Warunek rozpoczęcia

Projekty 0–2 mają status ukończony. Repo pilotażowe i trzy zadania zostały wskazane w Projekcie 0.

### Zakres zmian

1. Dodać jeden project contract dla repo pilotażowego.
2. Dodać wąską allowlistę repo, gałęzi, ścieżek i komend.
3. Zdjąć zakaz external project execution tylko dla tego jednego przypiętego repo i tylko dla tego use case’u.
4. Uruchomić trzy zadania bez rozszerzania platformy.
5. Zebrać raport wartości dla każdego zadania.
6. Nie scalać wyniku automatycznie.

### Raport pilotażowy

Każda próba zapisuje:

```text
PILOT ID:
BASE COMMIT:
TASK:
EXPECTED RESULT:
FINAL STATUS:
TEST RESULT:
FILES CHANGED:
HUMAN DECISIONS:
HUMAN EDITS AFTER EXECUTOR:
TIME TO REVIEW:
WOULD USER ACCEPT RESULT: YES / NO
POLICY VIOLATION: YES / NO
NOTES:
```

### Testy Projektu 3

#### `P3-T01 — Baseline failure`

Każdy task ma powtarzalnie nieprzechodzący test przed zmianą.

#### `P3-T02 — Correct repair`

Po zmianie wskazany test przechodzi, a pozostały zestaw testów nie regresuje.

#### `P3-T03 — Branch isolation`

Zmiana istnieje wyłącznie na osobnej gałęzi lub worktree; bazowa gałąź pozostaje bez zmian.

#### `P3-T04 — Path integrity`

Żaden plik poza allowlistą nie jest zmodyfikowany.

#### `P3-T05 — Review sufficiency`

Człowiek może podjąć decyzję na podstawie raportu, diffu i logów bez odtwarzania ukrytego stanu procesu.

#### `P3-T06 — Human intervention count`

Do wykonania tasku potrzebna jest najwyżej jedna decyzja semantyczna człowieka po zatwierdzeniu wejścia.

#### `P3-T07 — Accepted usefulness`

Co najmniej dwa z trzech wyników są zaakceptowane jako użyteczne bez ręcznego przepisywania rozwiązania.

#### `P3-T08 — Work reduction`

Dla co najmniej dwóch z trzech prób praca człowieka jest mniejsza niż wykonanie tej samej naprawy bez Executora.

#### `P3-T09 — Zero silent policy violation`

Nie występuje żadna niezgłoszona zmiana niedozwolonego pliku, commita, komendy ani środowiska.

### Bramka wyjścia

`CONTINUE`, gdy:

- minimum 2/3 wyników jest poprawnych i użytecznych;
- wszystkie trzy wykonania są jawnie raportowane;
- nie wystąpiła cicha zmiana poza polityką;
- praca człowieka faktycznie maleje.

`STOP`, gdy:

- mniej niż 2/3 wyników jest użytecznych;
- operator wykonuje większość napraw ręcznie;
- system wymaga więcej review niż zwykła zmiana;
- dalsza poprawa wymaga budowy szerokiej platformy zamiast poprawienia jednego przepływu.

### Powiązane ryzyka

`FIN-001`, `FIN-002`, `FIN-005`, `FIN-006`, `FIN-008`.

---

## Projekt 4 — Redukcja złożoności i release candidate 1.0

### Cel

Po pilocie usunąć wszystko, co nie było potrzebne do realnego wyniku, i zamknąć wersję 1.0.

### Czas maksymalny

2–3 dni robocze.

### Zakres zmian

1. Sporządzić mapę rzeczywiście używanej ścieżki wykonania.
2. Usunąć albo odłączyć z krytycznej ścieżki komponenty niewykorzystane przez kanoniczny use case.
3. Dla 1.0 uprościć dowód do:
   - wejściowego commita;
   - tasku i approval record;
   - surowego wyniku workera;
   - diffu;
   - komend i logów;
   - wyniku testów;
   - końcowego statusu.
4. Zdecydować, czy aktualna maszyna stanów jest proporcjonalna do use case’u.
5. Nie wykonywać migracji skomplikowanego formatu, jeżeli 1.0 nie ma danych produkcyjnych.
6. Zaktualizować README tak, aby opis implementacji odpowiadał faktycznie wykonanej ścieżce.
7. Utworzyć release acceptance test i checklistę 1.0.

### Czego implementer ma się nauczyć

- usuwać kod, który nie zarabia na swoje utrzymanie;
- odróżniać kompatybilność produkcyjną od przywiązania do prototypu;
- oceniać architekturę po użytej ścieżce, nie po liczbie mechanizmów;
- kończyć wersję bez obowiązku natychmiastowego projektowania 2.0.

### Testy Projektu 4

#### `P4-T01 — Release acceptance`

Jedno polecenie wykonuje pełny kanoniczny use case na kontrolowanym zadaniu release.

#### `P4-T02 — Full regression`

Przechodzą wszystkie testy kontraktów, polityki, state machine, sandboxu i pionowego przepływu, które nadal dotyczą 1.0.

#### `P4-T03 — No unused mandatory subsystem`

Każdy komponent wymagany do startu lub zakończenia runu jest wykonywany przez acceptance test. Nieużywany komponent nie może blokować wydania.

#### `P4-T04 — Documentation truth`

Każde `IMPLEMENTED` w README posiada wskazany test. Każde niewdrożone twierdzenie jest oznaczone `NOT IMPLEMENTED`, `DEFERRED` albo usunięte.

#### `P4-T05 — Clean install`

Na czystym środowisku zgodnym z wymaganiami repo można uruchomić testy i kanoniczny use case na podstawie README.

#### `P4-T06 — Failure honesty`

Przynajmniej jeden kontrolowany błąd workera, sandboxu, testu i polityki daje odrębny, prawidłowy status.

#### `P4-T07 — Risk register closure`

Każde ryzyko `FIN-001`–`FIN-008` ma status oparty na ścieżce do testu lub raportu. Ryzyka bez dowodu pozostają `OPEN` albo `PARTIAL`.

### Bramka wyjścia

`RELEASE 1.0`, gdy wszystkie wymagania 1.0 i testy `P4-*` są zaliczone oraz pilot spełnił własną bramkę.

`STOP AS PRODUCT`, gdy pilot nie wykazał redukcji pracy człowieka. W takim przypadku zachować wartościowe komponenty jako bibliotekę walidacji i sandbox, ale nie rozwijać dalej platformy wykonawczej.

### Powiązane ryzyka

Wszystkie `FIN-001`–`FIN-008`.

---

## Projekt 5 — M3 i zewnętrzna granica zaufania, opcjonalnie po 1.0

### Cel

Rozwijać M3 wyłącznie wtedy, gdy realne użycie 1.0 ujawni konkretny skutek, którego nie można zaakceptować bez silniejszej autoryzacji, replayu lub niezależnej weryfikacji.

### Warunek rozpoczęcia

Wymagane są równocześnie:

1. działająca wersja 1.0;
2. co najmniej jeden zaakceptowany use case produkcyjny;
3. zapisany model zagrożeń;
4. konkretny właściciel ryzyka;
5. opis skutku biznesowego lub technicznego;
6. dowód, że prostsza kontrola nie wystarcza.

Bez tych sześciu punktów M3 pozostaje `DEFERRED`.

### Podział M3

#### M3A — Jednorazowa autoryzacja i atomowa konsumpcja

Budować tylko dla działań, których ponowne wykonanie powoduje realny skutek uboczny.

Testy:

- równoległa próba konsumpcji jednego approval record;
- ponowne użycie po restarcie procesu;
- awaria między rezerwacją a zapisem wyniku;
- jednoznaczna relacja approval → action attempt.

#### M3B — Związanie autoryzacji z wynikiem

Budować tylko wtedy, gdy approval musi autoryzować konkretny rezultat, a nie tylko próbę.

Testy:

- podmiana result tokenu;
- wynik z innego tasku, commita lub runu;
- częściowy skutek bez końcowego result binding;
- retry, który nie nadpisuje historii pierwszej próby.

#### M3C — Niezależny verifier, holdout i replay

Budować tylko wtedy, gdy istnieje rzeczywiście niezależna domena zaufania.

Minimalna granica niezależności musi obejmować co najmniej:

- osobną tożsamość wykonawczą;
- osobne poświadczenia;
- brak prawa zapisu przez Executora do danych holdoutu;
- osobne miejsce trwałego zapisu;
- możliwość weryfikacji bez pamięci procesu Executora;
- jawnego właściciela i procedurę rotacji kluczy;
- audytowalną odpowiedzialność za finalne poświadczenie.

Oddzielny katalog, SQLite albo klucz utworzony przez ten sam proces nie jest zewnętrzną granicą zaufania.

Testy:

- replay na nowym procesie i czystym środowisku;
- podmiana manifestu, blobu, receipt i klucza;
- brak dostępu Executora do modyfikacji holdoutu;
- utrata pamięci procesu między wykonaniem i weryfikacją;
- verifier odrzucający poprawnie podpisany, lecz semantycznie obcy wynik;
- pozytywna weryfikacja przeprowadzona przez inną tożsamość.

### Bramka wyjścia

M3 nie jest ukończony przez samo zaliczenie self-testu lokalnego. Ukończenie wymaga dowodu niezależnej domeny zaufania odpowiadającej zapisanemu modelowi zagrożeń.

---

# 7. Kolejność PR-ów

## PR-00 — Plan naprawczy i rejestr ryzyk

Zakres:

- ten dokument;
- odnośnik z README;
- brak zmian runtime.

Bramka:

- plan jest czytelny;
- nie deklaruje implementacji;
- każdy etap ma testy i warunek zatrzymania.

## PR-01 — Zamknięty use case i pilot fixtures

Zakres:

- wskazanie repo pilotażowego;
- trzy deterministyczne zadania;
- raport pilotażowy;
- aktualizacja statusów `FIN-*` bez implementowania runtime.

## PR-02 — `execute-task` na deterministycznym fixture

Zakres:

- jeden orchestrator;
- jeden typ działania;
- testy `P1-*`;
- bez realnego modelu.

## PR-03 — Jeden rzeczywisty worker

Zakres:

- jeden konkretny adapter;
- testy `P2-*`;
- brak frameworka providerów.

## PR-04 — Jeden przypięty projekt pilotażowy

Zakres:

- wąski project contract i policy;
- trzy wykonania;
- raporty `PILOT-*`;
- testy `P3-*`.

## PR-05 — Redukcja i release candidate 1.0

Zakres:

- usunięcie zbędnej złożoności;
- release acceptance;
- aktualizacja prawdy dokumentacyjnej;
- końcowa decyzja `RELEASE / STOP AS PRODUCT`.

## PR-M3-*

Nie rozpoczynać przed wydaniem 1.0 i spełnieniem warunków Projektu 5.

---

# 8. Globalna seria testów

Testy mają tworzyć piramidę dowodu, a nie listę niezależnych mechanizmów.

## Poziom A — Testy kontraktów i czystych funkcji

Sprawdzają:

- parsery;
- walidację pól;
- normalizację ścieżek;
- policy decisions;
- state transitions;
- status mapping.

Nie są dowodem działania produktu.

## Poziom B — Testy integracji komponentów

Sprawdzają:

- repo identity + policy;
- worktree + worker;
- worker result + diff validation;
- sandbox + tests;
- result + report;
- cleanup + restart.

## Poziom C — Testy pionowe na fixture

Jedno polecenie przechodzi cały przepływ. To pierwsza bramka produktu, ale nadal nie jest dowodem użycia zewnętrznego.

## Poziom D — Testy przeciwnicze

Obowiązkowo obejmują:

- niedozwoloną ścieżkę;
- inny commit;
- niepoprawny patch;
- fałszywą deklarację sukcesu workera;
- timeout;
- crash;
- brak Dockera;
- próbę wykonania na hoście;
- niepełny cleanup;
- powtórzenie tego samego tasku;
- niejawny stan z poprzedniego procesu.

## Poziom E — Pilot na realnym repo

Mierzy:

- poprawność;
- przydatność;
- liczbę decyzji człowieka;
- ręczne poprawki po Executorze;
- czas review;
- redukcję pracy;
- naruszenia polityki.

## Poziom F — Release acceptance

Jedno polecenie i jedna kontrolowana procedura udowadniają pełne zdanie wersji 1.0.

---

# 9. Kryteria natychmiastowego zatrzymania rozwoju

Rozwój produktu należy zatrzymać i wrócić do decyzji produktowej, gdy wystąpi dowolny z warunków:

1. kolejny milestone nie poprawia kanonicznego use case’u;
2. wymagany jest nowy ogólny framework przed działającym pionowym przepływem;
3. więcej czasu poświęca się na dowodzenie integralności niż na uzyskanie wyniku użytkownika;
4. dwa kolejne PR-y nie przynoszą nowego obserwowalnego wyniku;
5. pilot wymaga więcej ręcznej pracy niż zwykła naprawa;
6. status sukcesu zależy od deklaracji komponentu wykonującego;
7. dokumentacja opisuje funkcje bez testu i ścieżki wykonania;
8. zakres 1.0 rozszerza się w trakcie implementacji bez usunięcia elementu o podobnym koszcie;
9. zespół nie potrafi wskazać, który `FIN-*` zamyka aktualna praca.

---

# 10. Format opisu każdego przyszłego PR-a

```markdown
## Wynik użytkownika

## Zakres

## Poza zakresem

## Ryzyka FIN-* zmniejszane przez PR

## Failing test lub kontrprzykład przed zmianą

## Test pozytywny

## Testy negatywne

## Dowód wykonania

## Ręczne interwencje

## Złożoność dodana

## Złożoność usunięta

## Bramka CONTINUE / STOP

## Status ryzyk po PR
```

PR bez wypełnionej bramki i dowodu wykonania pozostaje draftem.

---

# 11. Definicja ukończenia Executor 1.0

Wersja 1.0 jest ukończona tylko wtedy, gdy wszystkie poniższe punkty są prawdziwe:

- [ ] jedno zdanie produktu nie zmieniło się podczas Projektów 1–4;
- [ ] istnieje jedno polecenie wykonujące cały przepływ;
- [ ] rzeczywisty worker tworzy zmianę;
- [ ] zmiana powstaje na osobnej gałęzi lub worktree;
- [ ] repo i commit wejściowy są przypięte;
- [ ] niedozwolone pliki i komendy są blokowane;
- [ ] testy wykonują się w sandboxie bez host fallbacku;
- [ ] raport zawiera diff, logi, testy i interwencje;
- [ ] brak zmiany i nieudana zmiana nie są sukcesem;
- [ ] wykonano trzy próby na realnym repo;
- [ ] minimum 2/3 prób dało użyteczny wynik;
- [ ] minimum 2/3 prób zmniejszyło pracę człowieka;
- [ ] nie wystąpiło ciche naruszenie polityki;
- [ ] wszystkie wymagane komponenty są używane przez acceptance test;
- [ ] README odróżnia `IMPLEMENTED`, `DEFERRED` i `NOT IMPLEMENTED`;
- [ ] rejestr `FIN-001`–`FIN-008` posiada dowody albo uczciwie pozostawione otwarte ryzyka;
- [ ] wydanie nie wymaga ukończenia M3;
- [ ] po wydaniu nie istnieje obowiązkowy następny milestone, aby 1.0 miało sens.

Jeżeli którykolwiek z punktów jest niespełniony, projekt może nadal być wartościowym eksperymentem lub biblioteką, ale nie spełnia definicji Executor 1.0.
