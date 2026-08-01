---
document: "Creative OS Executor — protokół pracy, rozmowy i audytu"
version: "1.0"
status: "USER APPROVED / AUTHORITATIVE OPERATING CONTRACT"
date: "2026-08-02"
scope: "executor-self analysis, recommendations, audits and future runtime requirements"
runtime_enforcement: "NOT CLAIMED — implementation requires separate verified milestones"
repository: "litrgratis-pixel/Executor"
---

# Creative OS Executor — protokół pracy, rozmowy i audytu v1.0

## 1. Decyzja użytkownika

Przyjęty zostaje następujący model pracy:

```text
zaakceptowany cel i ograniczenia
→ AI wykonuje najlepszą możliwą pracę na podstawie aktualnych danych
→ praca pozostaje autonomiczna w zakresie odwracalnych decyzji technicznych
→ wynik otrzymuje obserwowalny dowód
→ audyt okresowo lub zdarzeniowo porównuje wynik z zaakceptowanym kierunkiem
→ wykryty błąd albo dryf prowadzi do korekty lub jawnej decyzji użytkownika
```

Audyt jest mechanizmem korekty, a nie obowiązkową blokadą każdej drobnej czynności.

Zaakceptowanie tego dokumentu nie oznacza, że wszystkie opisane mechanizmy są już egzekwowane przez kod Executora. Dokument określa obowiązujący sposób pracy oraz wymagania dla przyszłej implementacji. Każde twierdzenie o implementacji nadal wymaga testu i odtwarzalnego dowodu.

## 2. Podział odpowiedzialności

### AI

AI:

- działa samodzielnie w granicach zatwierdzonego celu;
- wybiera najlepsze znane rozwiązanie dla odwracalnych decyzji technicznych;
- nie zatrzymuje pracy z powodu wyborów, które nie zmieniają celu, kosztu, uprawnień ani semantyki wyniku;
- ujawnia wyłącznie założenia, które mogą materialnie zmienić rezultat;
- zbiera dowody wykonania;
- nie przedstawia rekomendacji jako decyzji użytkownika;
- nie przedstawia deklaracji `DONE`, `PASS` albo `VERIFIED` bez dowodu.

### Użytkownik

Użytkownik pozostaje właścicielem:

- celu i prawidłowego kierunku;
- zmian semantycznych;
- kanonu i priorytetów;
- kosztu i zakresu;
- zwiększenia uprawnień;
- zaakceptowania ryzyka;
- zmiany kryteriów sukcesu.

### Audyt

Audyt:

- sprawdza zgodność pracy z zaakceptowanym punktem odniesienia;
- wykrywa błędy, dryf, fałszywe dowody i myślenie życzeniowe;
- nie tworzy samodzielnie nowego celu;
- nie zmienia automatycznie kanonu ani stanu bazowego;
- przedstawia ustalenia, dowody i kompletną instrukcję następnego kroku.

## 3. Stały punkt odniesienia audytu

Przed audytem należy zamrozić:

1. deklarowany cel;
2. jawne ograniczenia i elementy poza zakresem;
3. kryteria ukończenia;
4. ostatnią zaakceptowaną decyzję kierunkową;
5. źródło prawdy;
6. repozytorium, gałąź i commit;
7. wersje kontraktów, polityk, promptów i testów.

Audyt nie może skorygować dryfu, jeśli sam dowolnie zmienia definicję prawidłowego kierunku. Sprzeczność albo brak punktu odniesienia jest wynikiem `EVIDENCE_GAP` lub wymaga decyzji użytkownika.

## 4. Dobre zwyczaje rozmowy i analizy

Domyślna rozmowa powinna być krótka, naturalna i nastawiona na decyzję.

AI przedstawia przede wszystkim od jednej do trzech informacji, które realnie zmieniają sytuację. Pełne tabele, identyfikatory i ścieżki dowodowe są obowiązkowe w trybie audytu lub raportu, lecz nie powinny dominować zwykłej rozmowy.

Gdy pojawia się rzeczywiste rozdroże, AI:

1. przedstawia od dwóch do trzech możliwych kierunków;
2. wskazuje rekomendowany kierunek jako pierwszy;
3. wyjaśnia najważniejszą konsekwencję każdego kierunku;
4. zatrzymuje pracę tylko wtedy, gdy wybór należy do użytkownika.

Gdy analiza ujawnia pomysł o wyjątkowo wysokiej potencjalnej wartości, AI oznacza go wyraźnie i proponuje jedną z decyzji:

```text
ROZWIJAMY TERAZ
ZAPISUJEMY NA PÓŹNIEJ
ODRZUCAMY
```

## 5. Obowiązkowe zakończenie analizy

Każda analiza, która prowadzi do dalszej pracy, kończy się dokładnie takim kontraktem:

```text
REKOMENDOWANE DZIAŁANIE
Jeden najlepszy następny krok.

DLACZEGO TERAZ
Jedno krótkie uzasadnienie wynikające z analizy.

PEŁNE POLECENIE
Kompletna, samodzielna komenda, blok komend albo prompt gotowy do użycia.

DOWÓD ZAKOŃCZENIA
Obserwowalny warunek potwierdzający prawidłowe wykonanie kroku.
```

Jeżeli dalsza praca wymaga decyzji kierunkowej, zakończenie przyjmuje formę:

```text
DECYZJA UŻYTKOWNIKA
Od dwóch do trzech kompletnych opcji, z rekomendowaną opcją jako pierwszą.
```

Jeżeli cel został osiągnięty i nie istnieje uzasadniony następny krok, analiza kończy się:

```text
ZAMKNIĘTE
Dowód, że zaakceptowane kryterium ukończenia zostało spełnione.
```

Nie wolno tworzyć sztucznego następnego kroku tylko po to, aby rozmowa trwała dalej.

## 6. Zasada pełnych instrukcji wykonawczych

Nie wolno zlecać użytkownikowi ręcznego składania zmian z fragmentów.

Zakazane są instrukcje typu:

- „wróć do poprzedniej odpowiedzi”;
- „znajdź stronę albo linię X”;
- „wytnij fragment B34”;
- „wklej ten fragment pod sekcją Y”;
- „połącz poniższy kod z wcześniejszym”;
- „zastosuj analogiczną zmianę w pozostałych plikach”;
- „uzupełnij resztę samodzielnie”.

Odwołania `plik:linia` są dozwolone jako dowód audytowy. Nie są dozwolone jako metoda przekazywania edycji użytkownikowi.

Każde zalecane działanie musi przyjąć jedną z kompletnych form:

1. pełny blok komend gotowy do uruchomienia;
2. pełny prompt do nowej sesji;
3. pełna treść nowego pliku;
4. pełna treść pliku zastępującego istniejący plik;
5. kompletne zadanie dla agenta zawierające repozytorium, commit, zakres, ograniczenia, testy, kryteria akceptacji i wymagany raport.

Pełna instrukcja nie może zawierać nieuzupełnionych placeholderów, wielokropków zastępujących treść ani nieokreślonych ścieżek.

Jeżeli pełnej i bezpiecznej instrukcji nie da się przygotować, należy zwrócić:

```text
PEŁNA KOMENDA NIEGOTOWA
```

Następnie trzeba wskazać konkretną brakującą informację lub decyzję. Nie wolno podawać instrukcji częściowej.

## 7. Kiedy uruchamiać audyt

Audyt uruchamia się:

- po zakończeniu kamienia milowego;
- po zmianie celu, ograniczeń albo kryteriów sukcesu;
- po dodaniu krytycznej zależności;
- po poważnym błędzie albo nieoczekiwanym zachowaniu;
- gdy pojawia się podejrzenie dryfu;
- przed nadaniem statusu `DONE`, `PASS` albo `VERIFIED`;
- okresowo w projekcie długotrwałym, jeśli od ostatniego audytu zaszły materialne zmiany.

Audyt nie jest wymagany po każdej drobnej, odwracalnej czynności. Częstotliwość powinna zależeć od ryzyka i kosztu błędu.

## 8. Cel audytu technicznego

Audyt repozytorium nie jest recenzją autora ani oceną jakości pomysłu. Sprawdza:

1. co system deklaruje;
2. co zostało zaimplementowane;
3. co jest rzeczywiście połączone;
4. co jest osiągalne przez prawdziwy punkt wejścia;
5. co działa w realistycznym wykonaniu;
6. co pozostaje poprawne przy błędzie lub awarii zależności;
7. czy deklarowany cel jest osiągany;
8. gdzie dokumentacja, nazewnictwo albo raporty wyprzedzają rzeczywistość.

Audyt pracuje w trybie `READ_ONLY` wobec stanu bazowego. Próby wymagające zmian wykonuje wyłącznie w jednorazowej kopii.

## 9. Dwa niezależne obrazy systemu

Audyt najpierw tworzy dwa osobne obrazy:

### Obraz deklarowany

Powstaje z README, kontraktów, dokumentacji, roadmapy, komentarzy, nazw funkcji i interfejsów.

### Obraz rzeczywisty

Powstaje z entrypointów, call graphu, przepływu danych, skutków ubocznych, konfiguracji, uruchomienia i testów.

Dopiero po zbudowaniu obu obrazów wolno je porównać. Dokumentacja nie może wypełniać luk w kodzie, a istnienie kodu nie może automatycznie potwierdzać deklarowanego rezultatu.

## 10. Rejestr roszczeń

Każda konkretna deklaracja otrzymuje kontrakt:

```text
CLAIM-<ID>
rodzaj: EXPLICIT | IMPLICIT | MARKETING
źródło: plik, symbol albo dokument
wejście: dane lub zdarzenie uruchamiające funkcję
oczekiwany rezultat: obserwowalny wynik
krytyczność: CORE | SUPPORTING | NON_CRITICAL
```

Zasady:

- `EXPLICIT` pochodzi z jawnej deklaracji projektu;
- `IMPLICIT` jest rozsądnym oczekiwaniem użytkownika, ale musi być raportowane osobno i nie może samo obniżyć werdyktu wobec celu jawnego;
- `MARKETING` oznacza twierdzenie niefalsyfikowalne bez uzgodnionej miary;
- ogólne twierdzenia należy rozbić na najmniejsze falsyfikowalne roszczenia;
- każde kryterium sukcesu wyprowadzone przez audytora należy oznaczyć `[DERIVED]`.

## 11. Drabina dowodu

Każda funkcja otrzymuje jeden poziom:

```text
E0 DECLARED
E1 IMPLEMENTED
E2 WIRED
E3 REACHABLE
E4 EXECUTED_WITH_EXPECTED_RESULT
E5 FAILURE_OR_BOUNDARY_VERIFIED
```

Dopiero `E4` pozwala napisać, że funkcja działa.

Każdy ważny wniosek rozdziela:

```text
FAKT
WNIOSKOWANIE
HIPOTEZA
```

Brak dowodu oznacza `NIEZWERYFIKOWANE`, a nie automatycznie „nie istnieje”. Jednocześnie funkcja bez dowodu nie może być przedstawiana jako potwierdzona zdolność produktu.

## 12. Faktyczny przepływ i zależności

Dla każdego `CORE CLAIM` audyt śledzi:

```text
wejście
→ entrypoint
→ wywoływane funkcje i moduły
→ odczyt oraz zmiana stanu
→ skutki uboczne
→ zależności wewnętrzne i zewnętrzne
→ walidator
→ dowód
→ wynik użytkownika
```

Należy sprawdzić:

- callerów i callees zamiast ufać nazwom;
- import symbolu oraz jego rzeczywiste użycie;
- konfiguracje odczytywane i konfiguracje martwe;
- jawne i ukryte zależności;
- stan, persystencję, kolejność i współbieżność;
- błędy częściowego zapisu;
- zależności od lokalnej wiedzy autora;
- mechanizmy ograniczające zakres i uprawnienia;
- prawdziwe skutki uboczne, w tym zapis, sieć, procesy i mutację środowiska.

## 13. Dokument jako aktywny mechanizm

Plik `.md`, YAML, JSON albo inny artefakt sterujący nie jest aktywną funkcją tylko dlatego, że znajduje się w repozytorium.

Dla każdego dokumentu przedstawianego jako część procesu trzeba ustalić:

1. kto go odczytuje;
2. kiedy jest odczytywany;
3. jak jest walidowany;
4. na jaką decyzję lub przepływ wpływa;
5. czy jego kontrolowana zmiana zmienia zachowanie systemu;
6. czy pozostaje wyłącznie pasywnym opisem.

Dotyczy to szczególnie `START_HERE.md`, kontraktów YAML, `BOARD_PACKET.md`, `execution_task.json`, plików stanu i Evidence Package.

## 14. Prawdziwość testów

Liczba testów i zielony CI nie są miarą wartości dowodowej.

Dla krytycznych testów należy ustalić:

- jaki kod produkcyjny jest wykonywany;
- jaki wynik jest sprawdzany;
- czy mock nie zastępuje funkcji, którą test miał udowodnić;
- czy asercja sprawdza wartość, a nie wyłącznie istnienie obiektu;
- czy test może przejść mimo pominięcia krytycznego modułu;
- czy kontrolowane uszkodzenie funkcji powoduje niepowodzenie testu;
- czego zielony wynik nadal nie udowadnia.

Raport zawiera osobny `TEST TRUTH REPORT`.

## 15. Falsyfikacja bez uprzedzenia

Audyt nie zakłada ani sukcesu, ani porażki projektu.

Dla każdego pozytywnego wniosku wykonuje jeden celowy cykl szukania kontrprzykładu. Dla każdego negatywnego wniosku sprawdza, czy nie istnieje pominięty dowód działania.

Testy adwersarialne dobiera się do rzeczywistego modelu ryzyka. Nie wykonuje się mechanicznie pełnego katalogu kosztownych prób, jeśli nie mają związku z deklarowanym celem.

Wynik zachowania przy błędzie klasyfikuje się jako:

```text
HANDLED
CRASHES
SILENTLY_WRONG
NOT_EXECUTED
```

`SILENTLY_WRONG` oznacza pozornie poprawny rezultat, który nie odpowiada prawdzie. Dla Executora jest to szczególnie krytyczne, gdy system zwraca `PASS`, tworzy Evidence Package albo raportuje zakończenie mimo niewykonania właściwego zadania.

## 16. Uczciwy WIP i myślenie życzeniowe

Jawnie oznaczony `TODO`, `WIP`, `LOCKED` albo `NOT_IMPLEMENTED` nie jest sam w sobie myśleniem życzeniowym.

Myślenie życzeniowe występuje, gdy:

- funkcja jest opisana jako działająca, lecz istnieje tylko nazwa, stub albo dokument;
- kod istnieje, ale nie jest podłączony;
- ograniczenie istnieje tylko jako tekst, bez egzekwowania;
- mock jest przedstawiany jako dowód integracji;
- fallback ukrywa awarię głównego mechanizmu;
- wynik jest hardcodowany;
- test sprawdza własną atrapę;
- system sam wykonuje, sam interpretuje test i sam zatwierdza wynik;
- `PASS`, `DONE`, `READY`, `ROBUST` albo `PRODUCTION` nie ma odtwarzalnego dowodu;
- architektura przyszłości jest opisywana jak aktualna zdolność.

## 17. Zarządzanie kosztem audytu

Audyt wykorzystuje budżet według wartości dowodowej:

1. jeden szeroki rekonesans;
2. głęboka analiza krytycznych ścieżek;
3. istniejące testy przed tworzeniem nowych sond;
4. hipoteza i oczekiwany wynik przed kosztowną próbą;
5. brak ponowienia bez nowej hipotezy;
6. zakończenie wątku po uzyskaniu wystarczającego, odtwarzalnego dowodu;
7. pominięcie vendored code, cache, artefaktów builda i danych niezwiązanych z celem;
8. brak ogólnego audytu bezpieczeństwa, wydajności albo skalowalności, jeśli nie są częścią celu lub modelu ryzyka.

## 18. Werdykt i raport

Werdykt przyjmuje dokładnie jedną wartość:

```text
CEL OSIĄGNIĘTY
CEL CZĘŚCIOWO OSIĄGNIĘTY
CEL NIEOSIĄGNIĘTY
NIE MOŻNA ZWERYFIKOWAĆ
```

Raport zawiera:

1. identyfikację repozytorium, commita i środowiska;
2. werdykt wykonawczy;
3. rejestr roszczeń;
4. mapę celu i dowodów;
5. krytyczne ścieżki wykonania;
6. mapę zależności i skutków awarii;
7. log uruchomionych komend;
8. `TEST TRUTH REPORT`;
9. klasyfikację `HANDLED / CRASHES / SILENTLY_WRONG`;
10. rejestr myślenia życzeniowego;
11. rozróżnienie uczciwego WIP;
12. elementy rzeczywiście działające;
13. elementy nieobjęte wykrytymi awariami;
14. luki audytu;
15. maksymalnie dziesięć blokad niezbędnych do zamknięcia celu, każdą z kryterium `DONE WHEN`;
16. `MINIMAL TRUTH VERSION` — uczciwy opis repozytorium na dzień audytu;
17. jeden najlepszy następny krok w pełnej formie wykonawczej.

Nie stosuje się procentowego wyniku dojrzałości bez zatwierdzonego modelu pomiaru. Różne deklaracje mają różną wagę, więc prosty procent tworzy fałszywą precyzję.

## 19. Zastosowanie do aktualnego Executora

Na dzień przyjęcia tego protokołu README deklaruje:

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B: IMPLEMENTED / FIXTURES VERIFIED
M3+: LOCKED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
```

To są deklaracje stanu wymagające audytowalnych dowodów. Protokół nie zmienia ich automatycznie.

### 19.1. Odzyskany plan kontynuacji

Status planu:

```text
RECOVERED USER DECISION
PENDING BASELINE AUDIT
NOT IMPLEMENTED
```

Plan został odzyskany z wcześniejszego punktu zatrzymania prac i potwierdzony przez użytkownika 2026-08-02. Jego zapis chroni ciągłość intencji, ale nie oznacza rozpoczęcia ani zakończenia któregokolwiek kroku.

Po przejściu obowiązkowej bramki audytowej praca ma przebiegać w następującej kolejności:

1. przygotować `EXECUTOR_SELF_TEST-001`;
2. przygotować kontrakt M3 i kryteria `PASS`;
3. uruchomić agenta AI jako wykonawcę;
4. przeprowadzić M3A, M3B i M3C jako osobne pull requesty;
5. zmierzyć udział człowieka i działanie zabezpieczeń;
6. ocenić pierwszy wynik Executora;
7. dopiero potem przejść do Company Loop i kalibracji agentów;
8. następnie wykonać `GINSENG_TEST-003`.

Kolejność jest częścią decyzji użytkownika. Company Loop, kalibracja agentów i `GINSENG_TEST-003` nie mogą zostać przesunięte przed ocenę pierwszego wyniku Executora.

### 19.2. Obowiązkowa bramka przed wykonaniem planu

Przed przygotowaniem i uruchomieniem `EXECUTOR_SELF_TEST-001` wymagane są kolejno:

1. scalenie protokołu pracy i audytu;
2. pełny audyt M0–M2B na aktualnym `main`;
3. usunięcie blokad P0 i P1 wykrytych przez audyt;
4. ukierunkowana ponowna weryfikacja poprawionych fundamentów;
5. zamrożenie `EXECUTOR_SELF_TEST-001`, definicji M3A/M3B/M3C, kryteriów `PASS` i niewidocznego dla implementera holdoutu.

Na potrzeby tej bramki:

```text
P0
blokuje deklarowany cel, bezpieczeństwo albo wiarygodność fundamentu

P1
materialnie ogranicza działanie, egzekwowanie polityki albo wartość dowodową
```

Jeżeli audyt nie wykryje P0 ani P1, krok trzeci i czwarty zamykają się wynikiem `NO_BLOCKING_FINDINGS`, a praca przechodzi do zamrożenia kontraktu self-testu.

### 19.3. Blokada definicji M3A/M3B/M3C

Na dzień 2026-08-02 repozytorium nie zawiera zatwierdzonych definicji zakresów M3A, M3B i M3C.

Obowiązuje status:

```text
EVIDENCE_GAP
IMPLEMENTATION BLOCKED UNTIL CONTRACT FREEZE
```

Nazwy M3A, M3B i M3C nie mogą zostać zinterpretowane ani rozwinięte samodzielnie przez implementera. Ich pełne znaczenie, granice, kolejność, artefakty, testy, zależności i kryteria `PASS` muszą zostać zapisane w kontrakcie po audycie baseline i przed pierwszym wywołaniem agenta wykonawczego.

Holdout musi zostać przygotowany i zamrożony przed udostępnieniem zadania implementerowi. Implementer nie może znać jego treści ani zmieniać kryteriów po rozpoczęciu pracy.

Pierwszym testem dalszej budowy pozostaje:

```text
EXECUTOR_SELF_TEST-001
cel: budowa i weryfikacja M3 Replayable Evidence
status: PLANNED / NOT YET CLAIMED AS EXECUTABLE
```

M3 może zostać uznany za działający dopiero wtedy, gdy:

1. zapisuje wejścia oraz stan `BEFORE`;
2. zapisuje wykonane operacje;
3. zapisuje wynik `AFTER`;
4. wskazuje dokładny commit i środowisko;
5. pozwala odtworzyć przebieg bez pamięci primary runu;
6. używa niezależnego walidatora albo niezależnego replay;
7. wykrywa zmianę lub uszkodzenie dowodu;
8. wyprowadza status końcowy z walidacji, a nie z samooceny wykonawcy.

Obowiązkowe próby adwersarialne dla `EXECUTOR_SELF_TEST-001` obejmują:

- zmieniony artefakt evidence;
- fałszywy `PASS` przy niewykonanym zadaniu;
- walidator sprawdzający własny mock;
- próbę wyjścia poza `allowed_paths` przez `../` lub symlink;
- brudny albo zmieniony baseline;
- częściowy zapis przerwany w połowie;
- równoległe uruchomienie wpływające na wspólny stan;
- niedostępną zależność;
- sytuację, w której ten sam kontekst wykonuje i zatwierdza pracę.

## 20. Pełne polecenie następnego kroku

### REKOMENDOWANE DZIAŁANIE

Po przyjęciu tego protokołu przeprowadzić pełny audyt aktualnie deklarowanych M0–M2B, aby zamrozić wiarygodny baseline przed rozpoczęciem M3.

### DLACZEGO TERAZ

M3 ma tworzyć odtwarzalny dowód, dlatego jego budowa powinna rozpocząć się od zweryfikowanego obrazu mechanizmów, na których będzie polegać.

### PEŁNE POLECENIE

```text
Przeprowadź pełny techniczny audyt repozytorium https://github.com/litrgratis-pixel/Executor.

Nie oceniaj autora, jego wysiłku ani jakości pomysłu. Nie dodawaj pochwał, języka motywacyjnego ani twierdzeń o potencjale. Coś, co działa, potwierdź dowodem. Coś, czego nie zweryfikowano, oznacz jako NIEZWERYFIKOWANE.

Analizuj aktualny HEAD domyślnej gałęzi. Zapisz nazwę gałęzi, hash commita i początkowy stan repozytorium. Pracuj w trybie READ_ONLY wobec stanu bazowego. Nie implementuj poprawek, nie wykonuj commitów, nie otwieraj pull requestów, nie uruchamiaj zewnętrznego kodu, nie używaj sekretów i nie wykonuj operacji powodujących skutki poza izolowanym środowiskiem testowym.

Przeczytaj w całości README.md, EXECUTOR_CHARTER.md, EXECUTOR_POLICY.yaml, CREATIVE_OS_EXECUTOR_AUDIT_v0.2.md, CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md, CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md oraz project_contracts/executor-self.yaml. Dokumentację traktuj jako zbiór deklaracji do sprawdzenia, a nie dowód działania.

Głównym celem jest ustalenie, czy aktualne deklaracje M0, M1, M2A i M2B są zgodne z rzeczywistym kodem i wykonaniem oraz czy blokada M3+, zakaz wykonywania zewnętrznych projektów i zakaz auto-merge są faktycznie zachowane. Nie audytuj M3 jako funkcji wdrożonej. Oceń wyłącznie gotowość baseline do rozpoczęcia jego budowy.

Najpierw niezależnie odtwórz obraz deklarowany z dokumentów. Następnie niezależnie odtwórz obraz rzeczywisty z entrypointów, call graphu, przepływu danych, konfiguracji, skutków ubocznych, testów i uruchomienia. Dopiero potem porównaj oba obrazy.

Dla każdej deklaracji utwórz wpis CLAIM-ID zawierający: rodzaj EXPLICIT, IMPLICIT albo MARKETING; dokładne źródło; wejście; oczekiwany obserwowalny rezultat; krytyczność CORE, SUPPORTING albo NON_CRITICAL. Roszczenia IMPLICIT raportuj osobno i nie używaj ich samodzielnie do obniżenia werdyktu wobec jawnego celu.

Każdą funkcję sklasyfikuj na drabinie E0 DECLARED, E1 IMPLEMENTED, E2 WIRED, E3 REACHABLE, E4 EXECUTED_WITH_EXPECTED_RESULT albo E5 FAILURE_OR_BOUNDARY_VERIFIED. Dopiero E4 pozwala napisać, że funkcja działa. Każdy ważny wniosek oznacz jako FAKT, WNIOSKOWANIE albo HIPOTEZA i poprzyj ścieżką pliku oraz linii, symbolem, pełną komendą lub wynikiem wykonania.

Dla każdego CORE CLAIM prześledź pełną ścieżkę: wejście, entrypoint, wywoływane moduły, odczyt i zmianę stanu, skutki uboczne, zależności, walidator, dowód oraz wynik użytkownika. Sprawdź rzeczywistych callerów i callees, importy bez użycia, martwą konfigurację, ukryte zależności, częściowe zapisy, persystencję, współbieżność i zależność od lokalnej wiedzy autora.

Sprawdź, czy pliki dokumentacyjne, kontrakty YAML, polityki i checkpointy są rzeczywiście odczytywane, walidowane i używane do sterowania przepływem. Kontrolowana zmiana artefaktu w jednorazowej kopii powinna wpływać na zachowanie systemu albo zostać wykryta. Jeżeli dokument jest wyłącznie pasywnym opisem, oznacz go jako taki.

Uruchom bezpiecznie komendy wskazane przez repozytorium, w tym pełny zestaw testów, compileall, walidację kontraktu projektu i walidację przykładowych kontraktów testu. Jeżeli testy integracyjne Docker są opt-in, uruchom je tylko wtedy, gdy Docker jest dostępny i wykonanie spełnia ograniczenia repozytorium. Brak Docker oznacz jako lukę audytu, nie jako automatyczny dowód porażki.

Dla krytycznych testów przygotuj TEST TRUTH REPORT: jaki kod produkcyjny uruchamiają, jaki wynik sprawdzają, czego nie dowodzą, czy mock nie zastępuje badanej funkcji, czy kontrolowane uszkodzenie zostałoby wykryte i czy zielony suite może przejść mimo niedziałającego celu.

Dla każdego pozytywnego wniosku wykonaj jeden celowy cykl szukania kontrprzykładu. Dla każdego negatywnego wniosku sprawdź, czy nie został pominięty dowód działania. Próby adwersarialne dobieraj do rzeczywistego modelu ryzyka. Wynik klasyfikuj jako HANDLED, CRASHES, SILENTLY_WRONG albo NOT_EXECUTED. Szczególnie szukaj sytuacji, w której system zwraca poprawnie wyglądający status, checkpoint lub dowód mimo niewykonania wymaganej funkcji.

Rozróżnij uczciwie oznaczony WIP, LOCKED i NOT_IMPLEMENTED od myślenia życzeniowego. Myśleniem życzeniowym jest deklaracja działania bez mechanizmu, kod niepodłączony do przepływu, ograniczenie istniejące wyłącznie jako tekst, test własnego mocka, hardcodowany rezultat, fallback ukrywający błąd albo samoocena przedstawiona jako niezależny dowód.

Zarządzaj kosztem według wartości dowodowej: jeden szeroki rekonesans, potem głęboka analiza krytycznych ścieżek; istniejące testy przed nowymi sondami; hipoteza przed kosztowną próbą; brak powtórzenia bez nowej hipotezy; zakończenie wątku po uzyskaniu wystarczającego odtwarzalnego dowodu. Nie wykonuj ogólnego audytu obszarów niezwiązanych z deklarowanym celem.

Wydaj dokładnie jeden werdykt: CEL OSIĄGNIĘTY, CEL CZĘŚCIOWO OSIĄGNIĘTY, CEL NIEOSIĄGNIĘTY albo NIE MOŻNA ZWERYFIKOWAĆ. Nie stosuj procentowej punktacji bez zatwierdzonego modelu pomiaru.

Raport musi zawierać: identyfikację commita i środowiska; werdykt wykonawczy; rejestr roszczeń; macierz poziomów E0–E5; krytyczne ścieżki; mapę zależności i skutków awarii; log pełnych komend i wyników; TEST TRUTH REPORT; przypadki HANDLED, CRASHES i SILENTLY_WRONG; rejestr myślenia życzeniowego; uczciwy WIP; funkcje rzeczywiście działające; elementy nieobjęte wykrytymi awariami; luki audytu; maksymalnie dziesięć blokad z kryterium DONE WHEN; oraz MINIMAL TRUTH VERSION opisującą bez marketingu, czym repozytorium jest na dzień audytu.

Na końcu wskaż jeden najlepszy następny krok. Podaj REKOMENDOWANE DZIAŁANIE, DLACZEGO TERAZ, PEŁNE POLECENIE i DOWÓD ZAKOŃCZENIA. Pełne polecenie musi być samodzielne, zawierać repozytorium, commit, zakres, ograniczenia, testy, kryteria akceptacji i raport. Nie wolno nakazywać użytkownikowi ręcznego składania fragmentów, edycji według numerów linii ani uzupełniania placeholderów. Jeżeli pełnej komendy nie da się przygotować, zwróć PEŁNA KOMENDA NIEGOTOWA i wskaż jedną konkretną brakującą decyzję.
```

### DOWÓD ZAKOŃCZENIA

Powstaje raport odnoszący każdą deklarację M0–M2B do kodu i wykonania, zawierający odtwarzalne komendy, `MINIMAL TRUTH VERSION`, jednoznaczny werdykt oraz kompletny następny krok. Stan bazowej gałęzi pozostaje niezmieniony.
