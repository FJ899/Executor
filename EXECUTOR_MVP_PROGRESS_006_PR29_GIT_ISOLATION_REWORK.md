# Executor MVP Progress 006 — PR #29 Git Isolation REWORK

## Status

```text
PR #29: REWORK
READY: NO
MERGE: NO
STOP: NO

BASELINE SHA: 514ba20d67bd415e438440c62f47307709177a7f
TEST-ONLY SHA: ea3226dc2836d6287af7a080d12d3adeb7787298
RED RUN ID: 30767747711
CURRENT PR #29 HEAD: 75943321535b872a7cd242cd31e467a90df9d1cd
FIXED IMPLEMENTATION SHA: PENDING
GREEN RUN ID: PENDING
```

## Znalezisko

Przeciwnicza reprodukcja wykazała hostowe wykonanie lokalnych filtrów Git przed wejściem do Dockera. Checkout może jednocześnie pozostać czysty i wskazywać oczekiwany commit.

Test-only run potwierdził sześć klas naruszeń:

- bezpośrednie polecenia Git przeciwko wejściowemu checkoutowi;
- lokalny filtr `clean`;
- lokalny filtr `smudge`;
- lokalny filtr `process`;
- `include.path`;
- `includeIf`.

Job Docker i realne CASE-001–003 pozostały zielone. Oznacza to:

```text
FUNCTIONAL PILOT: WORKING
HOST GIT INPUT ISOLATION: FAILED
CURRENT CI AS ACCEPTANCE PROOF: INSUFFICIENT
```

## Niezmiennik

Przed utworzeniem repozytorium kontrolowanego przez Executora żaden proces uruchomiony przez Executora nie może używać wejściowego checkoutu ani jego `.git` jako repozytorium Git, cwd, argumentu, zmiennej środowiskowej ani pośredniego wejścia programu potomnego.

Po utworzeniu repozytorium kontrolowanego wszystkie operacje Git muszą działać wyłącznie w katalogu runu.

## Rozdzielone bramki

```text
INPUT MODEL COMPLIANCE
OBJECT IDENTITY
ORIGIN ANCHOR
GIT INPUT ISOLATION
INPUT IMMUTABILITY
```

Lokalny `origin` nie jest dowodem pochodzenia. Hash obiektu potwierdza tożsamość treściową, ale nie pochodzenie.

## Artefakty

PR #29 zawiera w `docs/pr29_git_isolation/`:

1. kartę bramki;
2. plan REWORK;
3. macierz testów bezpieczeństwa;
4. dziennik dowodów;
5. końcową bramkę.

Dołączono także reproduktor, output, raport bazowy i diagnostykę filtrów per polecenie Git.

## Następna praca

Nie wdrażać jeszcze hipotezy „sterylne repozytorium” ani fresh clone/fetch.

Najpierw:

```text
ustalić wspierany model wejścia
→ porównać controlled fresh clone/fetch z controlled offline import
→ zdefiniować SOURCE ACQUISITION NETWORK POLICY
→ zdefiniować WORKER EXECUTION NETWORK POLICY
→ zapisać ADR i model zagrożeń
→ dopiero potem wdrożyć minimalną naprawę
```

## Stan ryzyk

- techniczny benchmark CASE-001–003 pozostaje ważnym dowodem funkcjonalnym;
- konsolidacja runtime’u pozostaje poprawnym wynikiem strukturalnym;
- przyjęcie replacement runtime’u jest zablokowane;
- `FIN-001`–`FIN-007`: najwyżej `PARTIAL`;
- `FIN-008`: `OPEN`;
- AI worker i M3 pozostają zabronione do czasu formalnego `ACCEPT` PR #29.
