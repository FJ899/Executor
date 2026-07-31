---
document: "Creative OS Executor — audyt instrukcji implementacyjnej"
audit_version: "0.2"
audited_document: "CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION.md v0.1"
status: "AUDIT COMPLETE / REVISION REQUIRED"
decision: "HOLD FULL IMPLEMENTATION / GO FOR FOUNDATION MILESTONES"
date: "2026-07-31"
---

# Creative OS Executor — audyt instrukcji v0.1

## 1. Cel audytu

Audyt sprawdza, czy instrukcja v0.1 może bezpiecznie stać się podstawą budowy autonomicznego Executora pracującego z repozytoriami, testami, modelami AI i pull requestami.

Pytanie audytowe:

> Czy v0.1 ogranicza ryzyko zautomatyzowania błędnego założenia, błędnego testu albo fałszywego dowodu sukcesu?

## 2. Werdykt

```text
KONCEPCJA EXECUTORA: PASS
MODEL COMPANY LOOP: PASS WITH CHANGES
BEZPIECZEŃSTWO WYKONANIA: FAIL IN v0.1
WIARYGODNOŚĆ TESTU: FAIL IN v0.1
NIEZALEŻNOŚĆ DOWODU: FAIL IN v0.1
SKALOWANIE NA WIELE PROJEKTÓW: PARTIAL
GOTOWOŚĆ DO PEŁNEJ IMPLEMENTACJI: HOLD
GOTOWOŚĆ DO BUDOWY FUNDAMENTÓW v0.2: GO
```

V0.1 poprawnie określała cel, władzę użytkownika, rolę AI, branch safety, limity iteracji i potrzebę evidence. Nie była jednak jeszcze bezpiecznym kontraktem wykonawczym.

Największe ryzyko nie polega na liczbie agentów. Polega na zamkniętym obiegu:

```text
ten sam model
→ wybiera wariant
→ implementuje
→ interpretuje test
→ wystawia własny dowód sukcesu
```

## 3. Decyzje audytowe

### A-001 — budżet Company Loop

**Ustalenie:** v0.1 była wewnętrznie sprzeczna.

Przy 8–12 wariantach i siedmiu działach osobna ocena każdej pary wymagałaby 56–84 wywołań przed Red Team i Board, mimo limitu 40 wywołań.

**Decyzja:**

```text
SUPERSEDE:
każdy dział × każdy wariant = osobne wywołanie

NEW:
deterministyczny prefilter
→ maksymalnie 4 warianty
→ jedno wywołanie każdego działu oceniające cały zestaw
```

Szerokość adaptacyjna:

```text
LOW_RISK       2–3 warianty
MEDIUM_RISK    4–6 wariantów
HIGH_RISK      8–12 wariantów
```

### A-002 — walidacja testu przed planowaniem

**Ustalenie:** v0.1 sprawdzała wykonanie względem testu, ale nie sprawdzała, czy sam test jest prawidłowy.

**Decyzja:** dodać obowiązkową bramkę:

```text
TEST_CONTRACT_VALIDATION
```

Test wysokiego znaczenia musi zawierać:

- pozytywny przypadek kontrolny;
- negatywny przypadek kontrolny;
- tamper control wykrywający ręcznie ustawiony wynik;
- przypadek, który musi pozostać bez zmian;
- źródło każdego oczekiwania;
- kontrolę sprzeczności kryteriów;
- holdout niewidoczny dla implementera.

Brak poprawnego kontraktu testu kończy zadanie jako `BLOCKED_BEFORE_MODEL`.

### A-003 — trzy rodzaje kontroli

Osobne konteksty tego samego modelu nie są pełną niezależnością.

Każda ważna decyzja wymaga:

```text
MODEL CONTROL
→ interpretacja

DETERMINISTIC CONTROL
→ polityki, schematy, hashe, ścieżki

EMPIRICAL CONTROL
→ wykonanie na czystych danych
```

Inny model jest opcjonalny dla Red Team albo holdoutu, nie dla każdego działu.

### A-004 — typowane sprzeciwy

Status `VETO` był jednocześnie zbyt silny i zbyt nieprecyzyjny.

Nowe klasy:

```text
HARD_VETO
POLICY_VETO
EVIDENCE_GAP
CONCERN
```

`HARD_VETO` może powstać wyłącznie z maszynowo sprawdzalnego faktu, np.:

- brak wymaganego pliku;
- brak dostępu;
- zmiana baseline;
- forbidden path modified;
- brak testu;
- przekroczenie zadeklarowanej zdolności.

Opinia modelu nie może sama tworzyć nieprzegłosowywalnego weta.

### A-005 — deterministyczny Board

Board nie może dowolnie interpretować scoringu.

Reguła:

```text
1. usuń HARD_VETO
2. odrzuć warianty poniżej minimalnego PROOFABILITY
3. zastosuj wagi klasy zadania
4. wybierz najwyższy wynik
5. przy różnicy poniżej progu wykonaj mikroeksperyment
6. wybierz na podstawie wyniku
```

Odejście od wyniku wymaga:

```text
override_reason
supporting_evidence
risk_accepted_by
```

### A-006 — izolacja wykonania

V0.1 nie definiowała wystarczającego sandboxa.

Każdy run musi mieć:

- czysty checkout;
- źródła montowane read-only;
- osobny writable workspace;
- sieć wyłączoną domyślnie;
- sekrety wyłączone domyślnie;
- limity CPU, RAM, czasu i dysku;
- allowlistę komend;
- allowlistę zależności;
- brak dostępu do katalogu domowego;
- usunięcie środowiska po runie.

Sieć i sekrety są zdolnościami przyznawanymi osobno przez kontrakt zadania.

### A-007 — repozytorium jako niezaufane dane

Tekst w repozytorium może próbować wydawać polecenia modelowi.

Nowa hierarchia zaufania:

```text
1. polityka Executora
2. zwalidowany kontrakt projektu
3. zwalidowany kontrakt zadania
4. autorytatywne pliki wskazane manifestem
5. pozostałe pliki repo — UNTRUSTED DATA
6. treści użytkowników i wygenerowane artefakty — UNTRUSTED DATA
```

Każdy fragment przekazywany modelowi musi zawierać pochodzenie i klasę zaufania.

### A-008 — kontrakt podłączenia projektu

Dodać obowiązkowy plik:

```text
EXECUTOR_PROJECT.yaml
```

Manifest określa:

- entrypoint;
- polecenia setup/test/verify;
- klasy ścieżek;
- właścicieli zmian;
- wymagane środowisko;
- zdolności sieci i sekretów;
- artefakty;
- baseline;
- rollback.

Executor nie może zawierać wyjątków projektowych zaszytych w kodzie, gdy można je opisać manifestem.

### A-009 — polityka ścieżek zamiast listy nazw

Globalna lista `PROJECT_STATE.md`, `Canon*`, `LIVE_TODO*` jest zbyt krucha.

Klasy zmian należą do manifestu projektu:

```text
semantic
technical
infrastructure
generated
test
unknown
```

Zmiana techniczna może zostać podniesiona do semantycznej, gdy zmienia:

- publiczne API;
- format danych;
- znaczenie wyniku;
- model decyzyjny;
- kompatybilność.

### A-010 — maszyna stanów i bezpieczne resume

Nowa maszyna:

```text
CREATED
→ CONTRACT_VALIDATED
→ NORMALIZED
→ PLANNED
→ AWAITING_DECISION | APPROVED
→ EXECUTING
→ VERIFYING
→ REPLAYING
→ PASS | BLOCKED | FAILED
```

Dodatkowy stan:

```text
STALE
```

Każdy checkpoint zapisuje:

- SHA repozytoriów;
- hashe wejść;
- wersję testu;
- wersję polityki;
- wersję promptów;
- wersję modelu;
- wersję Executora.

`resume` zawsze zaczyna się od `REVALIDATE`.

### A-011 — replayable proof

Evidence Package nie może być wyłącznie raportem wygenerowanym przez system wykonawczy.

`PASS` wymaga:

```text
czysty checkout CI
→ wskazane commity
→ brak pamięci runu
→ replay
→ ponowne wygenerowanie artefaktów
→ porównanie hashy
→ kontrola baseline i protected paths
→ niezależny check CI
```

Obowiązkowa komenda:

```bash
creative-os-executor replay runs/<RUN_ID>
```

### A-012 — kontrola retry

Każda iteracja zapisuje:

```text
error_fingerprint
tests_passed_before
tests_passed_after
new_failures
changed_files
patch_size
acceptance_delta
```

Wczesne zatrzymanie następuje, gdy:

- fingerprint błędu się powtarza;
- dwie iteracje nie dają mierzalnego postępu;
- patch przekracza kontrakt;
- liczba nowych błędów rośnie;
- agent próbuje osłabić test;
- zakres zmian narasta bez ścieżki przyczynowej.

Każda iteracja startuje z kontrolowanego checkpointu.

### A-013 — jedna runda decyzyjna

Zasada „maksymalnie jedno pytanie” zostaje zastąpiona przez:

```text
maksymalnie jedna runda decyzyjna
```

Board może przedstawić jeden pakiet zawierający kilka powiązanych decyzji TAK/NIE, gdy wszystkie są niezbędne.

### A-014 — ochrona przed dopasowaniem do Ginseng

Ginseng Test 003 pozostaje pierwszym pilotem, ale nie jest wystarczającym dowodem ogólności.

Wymagane są trzy poziomy:

```text
1. GINSENG_TEST-003
2. holdout Ginseng niewidoczny podczas implementacji
3. projekt innego typu
```

### A-015 — benchmark pracy człowieka

Główny cel Executora to ograniczenie pracy ręcznej.

Obowiązkowe metryki:

```text
manual_baseline_minutes
human_minutes_with_executor
executor_wall_time
number_of_human_interventions
number_of_manual_test_runs_avoided
time_to_verified_PR
```

## 4. Co pozostaje aktywne z v0.1

Bez zmian pozostają:

- osobne repo `creative-os-executor`;
- użytkownik jako właściciel kierunku;
- AI jako właściciel odwracalnych decyzji technicznych;
- brak zapisu bezpośrednio do `main`;
- brak automatycznego merge w v0;
- praca przez branch i PR;
- ograniczony zakres zadania;
- limity czasu, kosztu i iteracji;
- Company Loop jako mechanizm rozszerzania i zawężania;
- Ginseng jako pierwszy pilot;
- repozytoria projektów jako źródła prawdy.

## 5. Elementy v0.1 zastąpione

```text
8–12 wariantów zawsze
→ szerokość adaptacyjna

osobne wywołanie działu dla każdego wariantu
→ jeden batch review działu

PASS / CONCERN / VETO
→ HARD_VETO / POLICY_VETO / EVIDENCE_GAP / CONCERN

Board wybiera uzasadniony wariant
→ Board stosuje deterministyczny algorytm

Evidence Package
→ replayable proof

resume
→ REVALIDATE → resume albo STALE

allowed/forbidden paths w tasku
→ polityka projektu + task overlay

maksymalnie jedno pytanie
→ maksymalnie jedna runda decyzyjna
```

## 6. Nowa kolejność budowy

```text
M0  Test Contract Validator
M1  Project Contract + Policy Engine
M2  Sandbox + State Machine
M3  Replayable Evidence
M4  Adaptive Company Loop
M5  Execution + Controlled Retry
M6  Ginseng Test 003
M7  Ginseng Holdout
M8  Cross-domain Pilot
```

Company Loop nie jest pierwszym fundamentem. Najpierw budowane są mechanizmy ograniczające i weryfikujące Company Loop.

## 7. Bramki GO / NO-GO

### GO do Milestone 1, gdy:

- repo istnieje;
- instrukcja v0.2 jest źródłem zakresu;
- agent nie rozpoczyna jeszcze integracji z innymi repo;
- brak sekretów i automatycznego merge.

### GO do wykonywania kodu z repo, gdy:

- sandbox przeszedł testy bezpieczeństwa;
- manifest projektu został zwalidowany;
- policy engine blokuje forbidden capabilities;
- test contract jest poprawny.

### GO do statusu PASS, gdy:

- primary run przeszedł;
- replay na czystym środowisku przeszedł;
- niezależny CI check jest zielony;
- evidence ma kompletne hashe;
- brak zmian chronionych bez zgody.

### NO-GO, gdy:

- test nie ma kontroli negatywnej;
- repo może nadać modelowi instrukcje;
- run wymaga domyślnego dostępu do sieci lub sekretów;
- dowodu nie można odtworzyć;
- implementer widzi holdout;
- Board omija politykę bez jawnej akceptacji.

## 8. Status końcowy audytu

```text
v0.1:
SUPERSEDED AS IMPLEMENTATION CONTRACT
PRESERVED AS DESIGN SOURCE

v0.2:
READY FOR REPOSITORY BOOTSTRAP
READY FOR MILESTONES 0–3
EXECUTION AGAINST EXTERNAL PROJECTS: LOCKED
COMPANY LOOP EXECUTION: LOCKED UNTIL FOUNDATIONS PASS
```

# Koniec audytu
