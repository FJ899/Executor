# Independent Phase C Handoff

## Status

`PHASE B IMPLEMENTATION CANDIDATE / EXTERNAL AUTHORITY EVENTS AND REAL PILOTS PENDING`

P4 is not claimed. The executing agent is not the independent verifier.

## Human-selected constants

- DONE: P4 Repeatable Executor 1.0.
- Trusted front door/provider: external GitHub intake.
- Allowed actor/profile: `trust_profiles/github-p4-pilots.json`.
- Solution ownership: external Intelligence.
- Pilot repositories: `JTJ07/scriptops` and `JTJ07/creative-os-project-reconstructor`.
- Effects: branch, commit and draft PR only.
- Forbidden: merge, deploy, release, new secrets and paid services.

## Candidate implementation

- current GitHub issue/comment and target commit/tree verification;
- exact draft hash and `ACCEPT/MODIFY/REJECT` handling;
- durable SQLite authority consumption and terminal result binding;
- authority-free external solution candidate/proposal interface;
- bounded pilot sandbox runtime and draft-PR request artifact;
- two prepared pilot request bodies, exact solution candidates and patches;
- adversarial, concurrency, proposal and runtime tests.

## Observed pilot counterexamples

- ScriptOps at `daa6e5dc...`: lexicographic selection returned `v9` instead of `v10`; prepared fix returns `v10`, 4/4 tests pass and repository verifier passes.
- Reconstructor at `defc7b02...`: validator followed a required-file symlink outside the repository; prepared fix blocks it, 2/2 security tests and repository verifier pass.

Locators: `evidence/p4/PILOT_CANDIDATE_MANIFEST.json`, `evidence/p4/requests/` and `evidence/p4/candidates/`. Each candidate contains the full replacement text plus exact before/after hashes.

## Objective blockers before Phase C can begin

1. Two direct-human GitHub request issues do not yet exist.
2. Two exact, fresh, direct-human GitHub `ACCEPT` comments do not yet exist.
3. The implementation branch/draft PR and both pilot branch/draft PR writes require renewed GitHub tool approval after the current approval timeout.
4. Full GitHub Actions, Docker, wheel/CLI smoke and both real pilot runs must complete on published branches.

## Independent verification obligations

At the published candidate SHA, independently rerun G-01 through G-18 from `PROJECT_COMPLETION_MAP.md`, including the full forged/wrong-actor/edited/replayed/expired matrix, Docker isolation, atomic race and crash state, package installation, both real draft PRs, complete evidence replay and repository closure. Return exactly one verdict:

```text
PROJECT COMPLETION: PASS
PROJECT COMPLETION: BLOCKED
PROJECT COMPLETION: FALSE-COMPLETION
```

Only a later explicit human decision can accept Executor 1.0 or authorize any implementation/pilot merge or release.
