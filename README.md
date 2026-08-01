# Creative OS Executor

Repozytorium: `litrgratis-pixel/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Bezpieczny runtime wykonawczy dla Creative OS. Aktualny zakres obejmuje:

- **M0 — Test Contract Validator**;
- **M1 — Project Contract + Policy Engine**;
- **M2A — State Machine + Checkpointy**;
- **M2B — Izolowany Sandbox dla fixtures**.

Sandbox używa backendu Docker bez fallbacku do wykonania na hoście. Profil wymusza: read-only root, read-only source, osobny tmpfs workspace, brak sieci, brak sekretów, niedostępny HOME, non-root, usunięte capabilities, limity CPU/RAM/dysku/procesów/czasu oraz cleanup po runie.

M2B jest zweryfikowany wyłącznie na fixtures należących do repo Executora. Uruchamianie kodu z COS, ScriptOps, BPM:160 i innych repozytoriów nadal jest zabronione.

## Start

```bash
python -m unittest discover -s tests -v
python -m compileall -q executor
python -m executor.cli validate-project project_contracts/executor-self.yaml
python -m executor.cli validate-test test_contracts/examples/valid_test.yaml --base-dir tests/fixtures
```

Pliki `.yaml` używają składni JSON, która jest poprawnym podzbiorem YAML 1.2.

## Dokumenty sterujące

- `EXECUTOR_CHARTER.md` — misja, hierarchia zaufania i warunki zatrzymania;
- `EXECUTOR_POLICY.yaml` — deterministyczna polityka wykonania;
- `CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md` — kontrakt implementacyjny;
- `CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md` — zaakceptowane zasady autonomicznej pracy, rozmowy, pełnych instrukcji oraz audytu dowodowego.

Protokół pracy i audytu jest obowiązującym źródłem instrukcji dla projektu `executor-self`. Jego obecność nie jest dowodem implementacji mechanizmów runtime; egzekwowanie każdej reguły wymaga osobnego testu.

## Status

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B: IMPLEMENTED / FIXTURES VERIFIED
M3+: LOCKED
WORK AND AUDIT PROTOCOL: DOCUMENTED / RUNTIME ENFORCEMENT NOT CLAIMED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
```
