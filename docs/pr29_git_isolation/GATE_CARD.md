# PR #29 — Karta bramki REWORK

```text
PR: #29
BASELINE SHA: 514ba20d67bd415e438440c62f47307709177a7f
DECISION: REWORK
READY: NO
MERGE: NO
STOP: NO

HOST GIT FILTER ISOLATION: FAILED
CURRENT CI: GREEN BUT INSUFFICIENT
```

## Blocker

Hostowe operacje Git mogą uruchomić lokalne filtry `clean`, `smudge` lub `process` pochodzące z metadanych wejściowego checkoutu. Bazowy kontrprzykład potwierdza wykonanie filtrów `clean` i `smudge` przy zachowaniu czystego checkoutu i niezmienionego HEAD.

Dokładne przypisanie wykonań do poszczególnych poleceń Git pozostaje zadaniem diagnostycznym. Nie osłabia to nadrzędnego niezmiennika.

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
- istnieje osobny test-only SHA i udokumentowany czerwony run;
- wspierany model wejścia jest jawnie określony;
- wariant pozyskania źródła został wybrany w ADR;
- naprawa nie osłabia sandboxu;
- wszystkie testy macierzy są zielone na jednym nowym SHA;
- CASE-001–003 są zielone;
- wykonano niezależne review nowego SHA;
- nie znaleziono false success w zdefiniowanym modelu zagrożeń.

Dozwolona końcowa decyzja: `ACCEPT`, `REWORK` albo `STOP`.
