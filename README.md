# Creative OS Executor

Bezpieczny runtime wykonawczy dla Creative OS. Aktualny zakres obejmuje wyłącznie fundamenty:

- **M0 — Test Contract Validator**;
- **M1 — Project Contract + Policy Engine**.

Executor nie wykonuje jeszcze kodu z zewnętrznych repozytoriów, nie korzysta z sekretów, nie ma runtime sieciowego, nie implementuje Company Loop ani Execution Loop.

## Start

```bash
python -m unittest discover -s tests -v
python -m compileall -q executor
python -m executor.cli validate-project project_contracts/executor-self.yaml
python -m executor.cli validate-test test_contracts/examples/valid_test.yaml --base-dir tests/fixtures
```

Pliki `.yaml` w v0.2 używają składni JSON, która jest poprawnym podzbiorem YAML 1.2. Dzięki temu M0/M1 nie wymagają instalowania zależności z internetu.

## Status

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2+: LOCKED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
```
