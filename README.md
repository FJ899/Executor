# Creative OS Executor

Repozytorium: `litrgratis-pixel/Executor`.

Robocza nazwa systemu i pakietu Python: `creative-os-executor`. Nie oznacza ona osobnego repozytorium.

Executor jest runtime wykonawczym większego systemu Creative OS. Otrzymuje zatwierdzony kierunek i zamienia go w odwracalne, testowalne działanie. Nie zastępuje Ginsenga ani Company Loop, których rolą jest wyjście poza pierwszą ramę użytkownika, odkrycie potencjału, porównanie wariantów i przygotowanie decyzji.

Zabezpieczenia, sandbox i dowód są fundamentami uczciwego wykonania, ale nie stanowią głównego celu produktu. Nadrzędną definicję celu i granic zawiera `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`.

Aktualny zakres implementacji fundamentów obejmuje:

- **M0 — Test Contract Validator**;
- **M1 — Project Contract + Policy Engine**;
- **M2A — State Machine + Checkpointy**;
- **M2B — Izolowany Sandbox dla fixtures**.

Sandbox używa backendu Docker bez fallbacku do wykonania na hoście. Profil wymusza: read-only root, read-only source, osobny tmpfs workspace, brak sieci, brak sekretów, niedostępny HOME, non-root, usunięte capabilities, limity CPU/RAM/dysku/procesów/czasu oraz cleanup po runie. Polityka, source, obraz i własność kontenera są wiązane z niezmiennymi identyfikatorami oraz weryfikowane fail-closed.

M2B jest zweryfikowany wyłącznie na fixtures należących do repo Executora. Uruchamianie kodu z COS, ScriptOps, BPM:160 i innych repozytoriów nadal jest zabronione.

## Start

```bash
python -m unittest discover -s tests -v
python -m compileall -q executor
python -m executor.cli validate-project project_contracts/executor-self.yaml --policy EXECUTOR_POLICY.yaml --base-dir .
python -m executor.cli validate-test test_contracts/examples/valid_test.yaml --base-dir tests/fixtures --holdout-evidence tests/fixtures/holdout_evidence.json
```

Pliki `.yaml` używają składni JSON, która jest poprawnym podzbiorem YAML 1.2.

## Dokumenty sterujące

- `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md` — nadrzędny cel produktu, role Ginsenga, Company Loop, Creative OS, Executora i audytu oraz kolejność dalszej budowy;
- `EXECUTOR_CHARTER.md` — misja Executora, hierarchia zaufania i warunki zatrzymania;
- `EXECUTOR_POLICY.yaml` — deterministyczna polityka wykonania;
- `CREATIVE_OS_EXECUTOR_BUILD_INSTRUCTION_v0.2.md` — kontrakt implementacyjny;
- `CREATIVE_OS_EXECUTOR_WORK_AND_AUDIT_PROTOCOL_v1.0.md` — zaakceptowane zasady autonomicznej pracy, rozmowy, pełnych instrukcji oraz audytu dowodowego;
- `ACTION_AUTHORIZATION_PACKET_v1.0.md` — zamrożony terminalny kontrakt jednorazowej autoryzacji konkretnego działania.
- `M3_REPLAYABLE_EVIDENCE_CONTRACT_v1.0.md` — zamrożone definicje M3A/M3B/M3C, terminalnego `PASS` i `EXECUTOR_SELF_TEST-001`.

Protokół pracy i audytu jest obowiązującym źródłem instrukcji dla projektu `executor-self`. Jego obecność nie jest dowodem implementacji mechanizmów runtime; egzekwowanie każdej reguły wymaga osobnego testu.

Action Authorization Packet jest zamrożonym kontraktem semantycznym i posiada walidator. Poprawny pakiet oznacza wyłącznie `READY_FOR_ATOMIC_CONSUMPTION`. Nie jest dowodem wykonania. Atomowy ledger konsumpcji i związanie wyniku akcji należą do projektu M3.

Dokument celu produktu jest zatwierdzoną decyzją semantyczną, ale nie stanowi dowodu implementacji Ginsenga, Company Loop, `POTENTIAL_AND_DECISION_PACKET` ani M3.

## Status

```text
M0: IMPLEMENTED
M1: IMPLEMENTED
M2A: IMPLEMENTED
M2B: IMPLEMENTED / FIXTURES VERIFIED
M3A: IMPLEMENTED / INDEPENDENT HOLDOUT API AND AUTHENTICATED REPLAY
M3B: IMPLEMENTED / ATOMIC AAP LEDGER AND ACTION-RESULT BINDING
M3C: IMPLEMENTED / REPLAYABLE EVIDENCE AND TERMINAL PASS GATE
M3 CONTRACT: FROZEN
EXECUTOR_SELF_TEST-001: LOCAL PASS / INDEPENDENT CI REVIEW PENDING
PRODUCT PURPOSE: USER APPROVED / DOCUMENTED
POTENTIAL AND DECISION PACKET: LOGICAL CONTRACT / NOT IMPLEMENTED
ACTION AUTHORIZATION PACKET: CONTRACT FROZEN / VALIDATOR IMPLEMENTED / LEDGER PENDING M3
WORK AND AUDIT PROTOCOL: DOCUMENTED / RUNTIME ENFORCEMENT NOT CLAIMED
EXTERNAL PROJECT EXECUTION: FORBIDDEN
AUTO MERGE: DISABLED
```
