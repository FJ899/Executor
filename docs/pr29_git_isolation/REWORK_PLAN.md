# PR #29 — plan REWORK izolacji hostowych operacji Git

## Faza 1 — zamrożenie dowodów

1. Pozostawić PR #29 jako draft.
2. Nie wykonywać merge ani przejścia do ready.
3. Zapisać podatny baseline SHA.
4. Zapisać raport, reproduktor, output i wersję Git.
5. Nie zmieniać implementacji przed utworzeniem test-only commita i czerwonego runu.

Kryterium:

```text
REWORK widoczny
baseline SHA jednoznaczny
kontrprzykład odtwarzalny
dowody zapisane w repo
```

## Faza 2 — diagnostyka powierzchni wykonania

Każde polecenie badać osobno. Przed każdą próbą usunąć marker, przywrócić znany stan wejścia, wykonać dokładnie jedno polecenie i zapisać kod wyjścia, marker oraz trace procesów.

Badane polecenia:

1. `git status`
2. `git rev-parse`
3. `git remote`
4. `git cat-file`
5. `git ls-tree`
6. `git worktree add`
7. `git switch`
8. `git diff`
9. `git add`
10. `git commit`

Badane mechanizmy:

- `clean`;
- `smudge`;
- `process`;
- hooks;
- fsmonitor;
- textconv;
- external diff;
- `include.path`;
- `includeIf`.

Wynik tej fazy jest diagnostyczny. Niezależnie od wyników obowiązuje zakaz używania wejściowego `.git` przez procesy uruchamiane przez Executora.

## Faza 3 — test-only commit i czerwony run

Dodać testy bezpieczeństwa bez zmiany implementacji:

- lokalny filtr `clean`;
- lokalny filtr `smudge`;
- lokalny filtr `process`;
- lokalny `include.path`;
- lokalny `includeIf`;
- brak procesu Git otrzymującego wejściowy checkout lub `.git`;
- brak zmiany working tree;
- brak istotnej zmiany metadanych wejścia.

Wymagany łańcuch dowodowy:

```text
VULNERABLE_IMPLEMENTATION_SHA
TEST_ONLY_SHA
RED_RUN_ID
FIXED_IMPLEMENTATION_SHA
GREEN_RUN_ID
```

Naprawa nie może zostać wdrożona przed zapisaniem czerwonego runu.

## Faza 4 — model wejścia i ADR

Najpierw określić, które formy wejścia obsługuje Executor 1.0:

- kontrolowany fresh clone/fetch;
- zaufany niezmienny snapshot lub bundle;
- nieufny lokalny checkout.

Każdy niewspierany wariant musi być odrzucany fail-closed.

Porównać co najmniej:

### Wariant A — kontrolowany fresh clone/fetch

Executor sam tworzy repozytorium i pobiera dokładny commit. ADR musi określić dozwolone hosty i protokoły, zakaz lokalnych ścieżek, `file://`, `ext::`, niekontrolowanych remote helpers, hostowego SSH command, credential helpers i automatycznych submodules.

### Wariant B — kontrolowany import offline

Executor tworzy repozytorium z niezmiennego snapshotu wymaganych obiektów, bez przejmowania konfiguracji, hooks, info, refs i attributes wejścia.

### Wariant C — read-only alternate

Wariant analityczny, niepreferowany. Wymaga osobnego dowodu dotyczącego TOCTOU, symlinków, alternates i niezmienności object store.

Kryteria ADR:

- `INPUT MODEL COMPLIANCE`;
- `OBJECT IDENTITY`;
- `ORIGIN ANCHOR`;
- możliwość hostowego wykonania kodu;
- odporność na TOCTOU;
- zachowanie offline;
- wspierane formaty Git;
- złożoność i testowalność.

Sieć pozyskania źródła i sieć workera są oddzielnymi granicami:

```text
SOURCE ACQUISITION NETWORK POLICY
WORKER EXECUTION NETWORK POLICY
```

## Faza 5 — minimalna implementacja

Wszystkie procesy Git muszą przechodzić przez centralny wrapper i działać wyłącznie w repozytorium kontrolowanym przez Executora.

Wymagania:

- izolowane `HOME`;
- izolowane `XDG_CONFIG_HOME`;
- `GIT_CONFIG_NOSYSTEM=1`;
- `GIT_CONFIG_GLOBAL=/dev/null`;
- `GIT_ATTR_NOSYSTEM=1`;
- `GIT_TERMINAL_PROMPT=0`;
- usunięcie odziedziczonych `GIT_*`;
- ograniczony `PATH` i znana ścieżka binarnego Git;
- brak konfiguracji, hooks, attributes, filtrów i programów pomocniczych z wejścia;
- fail-closed dla cwd, argumentów i zmiennych wskazujących wejście.

Nie naprawiać problemu przez zgadywanie nazw filtrów.

## Faza 6 — poprawność i niezmienność wejścia

### INPUT MODEL COMPLIANCE

Zweryfikować, czy wejście odpowiada modelowi wybranemu w ADR, przypiętemu commitowi i wymaganym obiektom. Zmienione pliki, dodatkowe wpisy lub niewspierane metadane muszą być odrzucone albo pominięte zgodnie z ADR.

### INPUT IMMUTABILITY

Przed i po runie porównać manifest bezpieczeństwa obejmujący:

- obecność wpisów;
- typ wpisu;
- zawartość i hash plików;
- cele symlinków;
- istotne tryby i uprawnienia.

Nie porównywać domyślnie atime, wszystkich timestampów ani kolejności katalogów. Manifest wykrywa naruszenie; nie zastępuje read-only mountu lub niezmiennego snapshotu.

## Faza 7 — pełna walidacja

Na jednym nowym head SHA uruchomić:

1. wszystkie testy jednostkowe;
2. wszystkie testy integracyjne;
3. testy Docker;
4. CASE-001;
5. CASE-002;
6. CASE-003;
7. testy izolacji Git;
8. testy modelu wejścia;
9. testy niezmienności wejścia;
10. cleanup;
11. test braku terminalnego `PASS`.

## Faza 8 — adversarial acceptance

Zakres wynika z ADR i macierzy. Minimalnie obejmuje losowe nazwy filtrów, wiele filtrów jednocześnie, `clean`, `smudge`, `process`, include, odziedziczone zmienne Git, alternatywne formy wskazania `.git`, symlinki istotne dla wybranego wariantu, przerwanie importu oraz niekompletne lub zmienione wejście.

W testach bezpieczeństwa rejestrować rzeczywisty ślad procesów (`execve` lub równoważny), ponieważ reguły wrappera nie dowodzą samodzielnie zachowania programów potomnych.

## Faza 9 — niezależne review

Reviewer otrzymuje:

- baseline SHA;
- test-only SHA;
- RED_RUN_ID;
- fixed SHA;
- GREEN_RUN_ID;
- ADR;
- macierz testów;
- trace procesów;
- manifesty przed i po;
- wyniki CASE-001–003;
- cleanup.

Zielone CI nie jest samodzielnym dowodem izolacji.

## Faza 10 — decyzja

Dozwolone decyzje: `ACCEPT`, `REWORK`, `STOP`.

`ACCEPT` wymaga zablokowania wszystkich kontrprzykładów i klas ataku zdefiniowanych przez ADR i macierz. Formuła dowodowa brzmi:

```text
NO FALSE SUCCESS FOUND WITHIN THE DEFINED THREAT MODEL
```
