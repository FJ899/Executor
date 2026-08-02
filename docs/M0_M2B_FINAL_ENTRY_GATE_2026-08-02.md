# M0–M2B final entry gate — 2026-08-02

## Evaluated baseline

```text
main after PR #14 and PR #15
base merge: 78f5ba336652b5f67975d3e960a76d0a45d06a9d
verification branch: agent/final-m0-m2b-entry-gate
```

## Scope

This was a focused entry gate, not a new broad audit. It verified that the integrated M0–M2B foundations still fail closed across their most important trust boundaries:

- structural validity versus authoritative readiness;
- locked task inputs and placeholders;
- production holdout evidence;
- state-machine PASS boundary;
- sandbox policy provenance;
- terminal action issuer evidence.

## Final status

```text
P0 OPEN: 0
P1 OPEN: 0
KNOWN SILENTLY_WRONG IN VERIFIED SCOPE: 0
M3 ENTRY GATE: OPEN
```

This status means no unresolved P0/P1 was found in the targeted integrated scope after the complete repository suite and the real Docker security job. It is not a claim that all future defects are impossible.

## Persistent entry-gate invariants

The repository now contains a dedicated test that must keep proving:

1. structural project/task validity cannot claim authoritative execution readiness;
2. the authoritative Executor project is ready while placeholder GINSENG locks remain blocked;
3. a self-declared independent holdout verifier remains insufficient evidence;
4. the state machine cannot enter `PASS` before M3;
5. the sandbox rejects an unverified raw policy dictionary;
6. a self-declared `USER` cannot cross the terminal action boundary.

## Evidence required for this verdict

- full Python compile succeeds;
- the complete test suite succeeds, including the six entry-gate invariants;
- authoritative project, locked fixture task and evidence-backed validator fixture remain valid;
- placeholder task, traversal and missing holdout evidence remain blocked;
- real Docker isolation tests succeed;
- exact-name cleanup verification leaves no Executor test containers.

The final GitHub Actions run for PR #16 is the authoritative execution record for this report.

## Known limitations — intentionally moved into M3 scope

- independent holdout storage, trusted verifier and replay mechanism are not implemented;
- atomic Action Authorization Packet consumption ledger is not implemented;
- race-safe replay prevention and action-result binding are not implemented;
- state-machine transition to final `PASS` remains blocked;
- replayable evidence and action-result provenance are not implemented;
- external project execution remains forbidden.

These are not treated as open M0–M2B P0/P1 because the current runtime fails closed and does not claim that the missing mechanisms exist. They are mandatory design inputs for SOL MAX / WORK on M3, the independent holdout and `EXECUTOR_SELF_TEST-001`.

## Decision

The preparatory foundation work is complete. Further foundation hardening should require a new concrete counterexample. Without one, work proceeds to SOL MAX / WORK.
