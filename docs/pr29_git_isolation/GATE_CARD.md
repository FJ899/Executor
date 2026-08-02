# PR #29 — Karta bramki REWORK

```text
PR: #29
BASELINE SHA: 514ba20d67bd415e438440c62f47307709177a7f
DOCUMENTATION SHA: 9b71726eadd152984bd906bde2d8f0f8cd96dc39
TEST-ONLY SHA: ea3226dc2836d6287af7a080d12d3adeb7787298
RED RUN ID: 30767747711

DECISION: REWORK
READY: NO
MERGE: NO
STOP: NO

HOST GIT FILTER ISOLATION: FAILED
CURRENT CI: RED AS REQUIRED BY TEST-ONLY STAGE
IMPLEMENTATION FIX: NOT STARTED
```

## Blocker

Hostowe operacje Git uruchamiają lokalne filtry `clean`, `smudge` i `process` oraz konfiguracje wczytane przez `include.path` i `includeIf` z metadanych wejściowego checkoutu.

Test-only run na Git `2.54.0` potwierdził sześć oczekiwanych porażek bezpieczeństwa, podczas gdy realne CASE-001–003 oraz Docker pozostały zielone. Oznacza to, że funkcjonalność pilota działa, ale obowiązkowa izolacja hosta jest niespełniona.

## Niezmiennik bezpieczeństwa

Przed utworzeniem repozytorium kontrolowanego przez Executora nie wolno uruchamiać Git ani kodu pochodzącego z repozytorium przeciwko wejściowemu checkoutowi lub jego `.git`.

Po utworzeniu repozytorium kontrolowanego wszystkie operacje Git muszą działać wyłącznie na ścieżkach należących do katalogu runu Executora.

Zakaz obejmuje przekazanie wejścia przez:

- bieżący katalog procesu;
- `-C`;
- `--git-dir`;
- `--work-tree`;
- `GIT_DIR`, `GIT_WORK_TREE` i inne zmienne Git;
- automatyczne wykrywanie `.git` w katalogach nadrzędnych;
- skrypty pomocnicze, remote helpers i programy potomne.

## Rozdzielone właściwości

```text
INPUT MODEL COMPLIANCE:
Czy wejście odpowiada wspieranemu modelowi i przypiętemu commitowi?

INPUT IMMUTABILITY:
Czy Executor pozostawił wejście w tym samym istotnym stanie bezpieczeństwa?

OBJECT IDENTITY:
Czy użyto dokładnie oczekiwanych commitów, drzew i blobów?

ORIGIN ANCHOR:
Czy pochodzenie obiektów zakotwiczono poza nieufnym checkoutem?
```

URL `origin` z wejściowego `.git/config` jest nieufną deklaracją pomocniczą, nie dowodem pochodzenia.

## Exit criteria

- bazowy kontrprzykład jest zapisany i odtwarzalny;
- czerwony test-only run został zapisany;
- wspierany model wejścia jest jawnie określony;
- wariant pozyskania źródła został wybrany w ADR;
- naprawa nie osłabia sandboxu;
- wszystkie testy macierzy są zielone na jednym fixed SHA;
- CASE-001–003 są zielone;
- wykonano niezależne review fixed SHA;
- nie znaleziono false success w zdefiniowanym modelu zagrożeń.

Dozwolona końcowa decyzja: `ACCEPT`, `REWORK` albo `STOP`.
