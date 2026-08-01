# Creative OS Executor

Repozytorium: `litrgratis-pixel/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Bezpieczny runtime wykonawczy dla Creative OS. Aktualny zakres obejmuje:

- **M0 — Test Contract Validator**;
- **M1 — Project Contract + Policy Engine**;
- **M2A — State Machine + Checkpointy**.

M2A zapisuje append-only historię stanów, atomowe checkpointy i wykrywa `STALE` przed wznowieniem pracy. `PASS` jest niemożliwy bez przejścia przez `REPLAYING`.

Executor nadal nie wykonuje kodu z zewnętrznych repozytoriów, nie korzysta z sekretów, nie ma runtime sieciowego, nie implementuje Company Loop ani Execution Loop.

## Start

```bash
python -m unittest discover -s tests -v
python -m compileall -q executor
python -m executor.cli validate-project project_contracts/executor-self.yaml
python -m executor.cli validate-test test_contracts/examples/valid_test.yaml --base-dir tests/fixtures
```

Pliki `.yaml` używają składni JSON, która jest poprawnym podzbiorem YAML 1.2.

## Status

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B+: LOCKED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
```
