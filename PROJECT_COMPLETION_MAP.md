---
document: "Executor Project Completion Map"
version: "1.1"
status: "HUMAN SEMANTICALLY APPROVED / PHASE B ACTIVE"
date: "2026-08-17"
target_repository: "JTJ07/Executor"
baseline_branch: "main"
baseline_sha: "5e254811023553d1abe8bdbb3535b8150aaf19ad"
protocol: "JTJ07/Saddle/evidence/PROJECT_COMPLETION_AUTONOMY_TEST_PROTOCOL_2026-08-15.md"
phase: "B / IMPLEMENTATION AND EVIDENCE"
implementation_changes: "AUTHORIZED ON A WORK BRANCH / REVIEW REQUIRED"
---

# PROJECT COMPLETION MAP — Executor

## 0. Status and reading rules

This document is the human-approved completion map. `PHASE_B_AUTHORIZATION.md` freezes the selected semantic forks and activates work on a review branch. It is not product acceptance, a maturity claim, an implementation merge decision or a release decision. Historical Phase-A inventory/fork analysis is intentionally preserved below as provenance; later explicit Phase-B decisions and the 2026-08-17 G-04 clarification govern current semantics where older wording was unresolved.

Semantic labels used below:

- `FACT` — supported by current repository state or recorded GitHub evidence;
- `DECISION` — already selected by the human in an authoritative source;
- `HYPOTHESIS` — plausible interpretation requiring confirmation;
- `RECOMMENDATION` — proposed route, not authority.

Hard boundaries:

```text
REQUEST != CONTRACT
AI INTERPRETATION != USER INTENT
DRAFT CONTRACT != AUTHORIZED CONTRACT
CAPABILITY != AUTHORITY
EXECUTION != PROOF
AI RECOMMENDATION != HUMAN DECISION
```

The human selected HR-1 C, HR-2 A, HR-3 GitHub, HR-4 A and HR-5 C on 2026-08-16. The exact authority limits are recorded in `PHASE_B_AUTHORIZATION.md`. Final acceptance and release remain human-owned.

### 0.1 Adaptive completion control

`DECISION`, supplied by the human during review of this map:

`PROJECT_COMPLETION_MAP.md` is not a rigid workflow or a fixed queue of tasks. It freezes `GOAL`, the selected `DONE`, authority boundaries, known dependencies and evidence gates. It does not freeze the route taken between them.

After every material state change, the executing agent must reassess the whole project against the unchanged approved `GOAL` and `DONE`, then answer:

> What currently blocks the approved DONE most, and which available capability can remove that constraint best and most safely?

The operating loop is:

```text
MATERIAL STATE CHANGE
  -> RECONSTRUCT CURRENT WHOLE-PROJECT STATE
  -> COMPARE CURRENT STATE WITH UNCHANGED GOAL + DONE
  -> IDENTIFY THE HIGHEST-LEVERAGE CURRENT CONSTRAINT
  -> SELECT THE BEST-FIT AVAILABLE CAPABILITY
  -> EXECUTE THE SMALLEST SUFFICIENT SAFE ACTION
  -> RECORD EVIDENCE AND THE NEW STATE
  -> REASSESS THE WHOLE PROJECT AGAIN
```

The agent must not ask “which map item is next?” or execute a workstream merely because it appears earlier in this document. It must respect hard dependencies and authority gates, but may reorder, combine, replace or abandon implementation steps when current evidence shows a better route to the same approved DONE.

No specialized project, component, framework, agent or tool receives priority merely because it exists. Selection is capability-based: use the mechanism that removes the current constraint most effectively, safely and economically. If the base intelligence can do that better than a specialized project, use the base intelligence.

## 1. Evidence baseline

### 1.1 Canonical baseline

| Item | Observed state |
|---|---|
| Repository | `JTJ07/Executor` |
| Default branch | `main` |
| Baseline SHA | `728d23e56ec9f76fb7a37673ceb20efccf91e03d` |
| Baseline meaning | post-transfer current-self-identity reconciliation, merged by PR #58 |
| Canonical state rule | merged `main`; open branches and PRs are non-canonical |
| Target-repository state owner | `README.md`, according to `project_contracts/executor-self.yaml` |
| Current package version | `0.2.0` |
| Releases / tags | none observed |

### 1.2 Sources read

The analysis covered:

- product purpose and responsibility boundaries: `CREATIVE_OS_EXECUTOR_PRODUCT_PURPOSE_AND_BOUNDARIES_v1.0.md`, `EXECUTOR_CHARTER.md`;
- product and architecture: `docs/product/EXECUTOR_V1_PRODUCT_SPEC.md`, `docs/architecture/EXECUTOR_BUILD_MAP.md`;
- build order and implementation truth: `docs/EXECUTOR_BUILD_ORDER.md`, `docs/architecture/IMPLEMENTATION_INVENTORY.md`, merged code and tests;
- maturity definitions: `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`;
- request formation: `docs/governance/CONTRACT_FORMATION_BOUNDARY.md`, `docs/product/REQUEST_TO_CONTRACT_001.md`, `executor/request_to_contract.py`;
- GP001: `docs/product/GOLDEN_PATH_001_FIX_FAILING_TEST.md`, task/test contracts, `executor/gp001_contract.py`, `executor/gp001_runtime.py`, `tools/run_gp001_real_e2e.py`;
- authority and policy: `ACTION_AUTHORIZATION_PACKET_v1.0.md`, `EXECUTOR_POLICY.yaml`, `executor/action_authorization.py`, `executor/sandbox/policy_snapshot.py`;
- state, repository and sandbox paths: `executor/state_machine.py`, `executor/repository_access.py`, `executor/sandbox/docker.py` and their tests;
- all 62 current branch refs, all 18 open PRs, the single open issue, the recent merged history and current workflows;
- PR #59 and its full patch; draft stacks #17–#22, #29, #34, #36, #38 and #51–#57;
- current GitHub Actions evidence for PR #58 and PR #59.

### 1.3 Source authority caveat

`docs/governance/DOCUMENT_AUTHORITY.md` correctly says that merged code and tests are required to support implementation claims and that open PRs are not canon. Several document headers and status sections are stale despite later merges. This map therefore separates:

```text
PRODUCT PURPOSE
IMPLEMENTATION ON MAIN
OPEN CANDIDATE WORK
MATURITY / PROOF
```

## 2. Recovered project goal

### 2.1 Human-owned end goal

`DECISION`, recovered from the authoritative product-purpose document and accepted v1 product direction:

> Executor is the governed execution system of Creative OS. For its first product slice, a software developer can start with a bounded repository request in normal language; the system keeps interpretation separate from user authority, presents an explicit contract proposal, requires verified authorization before freezing it, executes only the frozen contract within policy, and returns truthful evidence and a review-required result.

The required product path is:

```text
BOUNDED HUMAN REQUEST
  -> INTERPRETATION / PROPOSAL (non-authoritative)
  -> REVIEWABLE DRAFT CONTRACT
  -> VERIFIED HUMAN DECISION
  -> EXACT AUTHORIZED + FROZEN CONTRACT
  -> BOUNDED SOLUTION PROPOSAL / PLAN
  -> EXACT EFFECT AUTHORIZATION
  -> ISOLATED EXECUTION
  -> OBJECTIVE EVIDENCE + REPLAY
  -> ACTION_COMPLETED_REVIEW_REQUIRED | BLOCKED | FAILED
  -> HUMAN REVIEW
```

### 2.2 Explicit non-goals

Completing Executor does not mean turning this repository into:

- all of Creative OS, Ginseng or Company Loop;
- a general-purpose autonomous coding agent;
- an arbitrary-domain task executor;
- an owner of human goals, project canon or strategic decisions;
- an automatic contract authorizer;
- an auto-merge or autonomous deployment system;
- a product that self-certifies correctness or acceptance;
- a generalized IAM, agent marketplace, multi-agent platform or provider-routing framework.

### 2.3 Completion-horizon decision history

`FACT`: the repository defines three materially different possible end states:

- the bounded Executor v1 product slice in `docs/product/EXECUTOR_V1_PRODUCT_SPEC.md`;
- `P3 — REAL VALUE MVP`, named by the authoritative ladder as the first true product MVP;
- `P4 — REPEATABLE EXECUTOR 1.0`, the first explicit repeatable 1.0 level.

`DECISION`: this Phase-A ambiguity is resolved. The human selected `HR-1 C — P4 REPEATABLE EXECUTOR 1.0` on 2026-08-16, as recorded in `PHASE_B_AUTHORIZATION.md`. The alternatives below remain historical decision context, not an open fork.

## 3. Current state

### 3.1 Complete and supported by evidence

`FACT`:

- M0 contract validation, M1 governance/policy, M2A state/checkpoint integrity and M2B Docker isolation exist on `main` with positive and negative tests.
- P0 is the only canonically claimed achieved product level.
- GP001 has a machine-readable exact task/test contract for one controlled external fixture.
- GP001 runtime checks exact repository/commit identity, reproduces the failing test, permits one exact file mutation, runs target and regression commands in Docker, verifies scope/protected material, emits a patch/report and ends at `ACTION_COMPLETED_REVIEW_REQUIRED`.
- GP001 real E2E and two-run replay were accepted through PRs #47 and #48 in the declared controlled-fixture scope.
- PR #58 reconciled the current Executor self identity to `JTJ07/Executor`; its `Verify Executor foundations` run `31539013966` and `GP001 replay repeatability` run `31539014065` succeeded.
- REQUEST_TO_CONTRACT_001 phase 1 was merged by PR #50. It preserves the verbatim request as the sole direct `USER` provenance, labels structured interpretation as `MODEL`, creates and critiques an exact canonical GP001 draft, exports a hash-bound non-executable authorization request, and fails closed at `AWAITING_VERIFIED_HUMAN_AUTHORIZATION`.
- Generic external-project execution and auto-merge remain disabled; default worker network and secrets remain empty.

### 3.2 Implemented but not equivalent to the final product path

`FACT`:

- The `main` CLI does not expose REQUEST_TO_CONTRACT_001. The class is reachable only through Python code/tests. PR #59 is one commit ahead of `main` and adds the bounded `form-gp001-request` CLI plus status documentation.
- PR #59 passed `Verify Executor foundations` (`31908746286`): 252 tests ran, 10 Docker opt-in tests were skipped in that job, all non-skipped tests passed, compile and validators passed. Its Docker security job ran 10 tests successfully. `GP001 replay repeatability` (`31908746347`) also passed.
- The real GP001 E2E is not a solver proof. `tools/run_gp001_real_e2e.py` contains the complete `OLD_BLOCK -> NEW_BLOCK` repair and passes an already prepared `AuthorizedFileMutation` to the runtime.
- `GP001Runtime.execute()` accepts a prepared exact mutation; it does not obtain a solution from a worker or planning component.
- Current request formation deliberately cannot consume `ACCEPT`, `MODIFY` or `REJECT`, cannot create `AUTHORIZED_AND_FROZEN`, and cannot hand a frozen contract to GP001.
- The AAP validator exists, but the authoritative AAP contract says real execution additionally requires atomic consumption and result binding. Current GP001 reports `authorization_consumption: RUN_LOCAL_REPLAY_GUARD_ONLY` and uses an in-memory packet-ID set. Persistent atomic consumption and action-result binding are not on `main`.
- Current GP001 produces a patch/report in a controlled workspace. It does not create a result commit or draft PR for a real user repository.

### 3.3 Incomplete, obsolete or contradictory state

`FACT`:

- No request-origin / human-identity trust provider is selected.
- No canonical verifier exists for externally rooted request-origin plus exact decision-event evidence, including freshness, replay and revocation semantics.
- Open draft PRs #51–#57 contain a large technology-agnostic trust analysis, but are explicitly unmerged, select no provider and select neither A1 nor strengthened A2.
- The current authoritative ladder still says the immediate target is old P1/PR #29, while later accepted build-order work moved to GP001 and REQUEST_TO_CONTRACT_001.
- `README.md`, build order, inventory, product spec, product-purpose status and several document headers contain stale claims such as old owner `litrgratis-pixel/Executor`, GP001 “not yet E2E”, or request formation “missing” despite PRs #47–#50.
- PR #59 corrects a useful subset of these contradictions but is still non-canonical and does not reconcile every authoritative document.
- The repository has 62 branches and 18 open PRs: one current non-draft PR (#59) and 17 drafts. Several draft descriptions explicitly say “never merge”; other stacks are 17 to 107 commits behind current `main` or based on other obsolete branches.
- The single open issue, #35, is explicitly a temporary PR #32 transport envelope that says it should be closed after payload recovery.
- There are 25 workflow files. Many are historical runner/controller diagnostics rather than current product gates.
- A push on the PR #59 branch produced an expected-but-noisy failure in `Trusted controller allocation test` run `31908727637`: the workflow compared current head `8254985...` with hard-coded historical workflow SHA `010dec8...`. The two current required PR workflows passed.
- `main` is reported as unprotected by the branch API. There are no tags or releases.

### 3.4 Non-canonical branch families

| Family | State relative to current `main` | Completion relevance |
|---|---|---|
| PR #59 / `codex/finish-request-formation` | 1 ahead, 0 behind | current bounded CLI/docs candidate; AI may integrate, revise or replace after map approval |
| PRs #51–#57 | stacked trust-design drafts; root is 17 commits behind and diverged | evidence for `HR-2`/`HR-3`, never automatic canon |
| PRs #17–#21 | old M3 design/implementation stack; root is 107 commits behind and diverged | salvage requirements/tests only if demanded by the selected completion path |
| PR #29 and PR #22 | old P1 pilot candidate/remediation; 107 commits behind and diverged | do not merge wholesale; compare useful acquisition/evidence mechanisms with current GP001 |
| PR #34 | old product-contract draft; 106 commits behind | may contain accepted semantic history, but conflicts must be reconciled rather than merged blindly |
| PRs #36/#38 and issue #35 | temporary evidence transport/generator work | close after preserving any still-required provenance |
| merged-feature branches | historical heads already represented in `main` history | delete or retain per branch-retention policy; they are not active roadmap work |

## 4. Precise definition of DONE

### 4.1 Common DONE invariant

The whole project may be called complete only when all common conditions below are true at one exact canonical SHA:

1. The human has accepted the recovered goal, selected `HR-1`, and resolved all active `HUMAN_REQUIRED` forks.
2. One canonical product/state document names the selected terminal level, supported task class, non-goals and exact evidence required for acceptance.
3. A bounded user can enter through the selected real front door without hand-authoring internal task YAML, AAPs, hashes or runtime objects.
4. Request-origin evidence and the exact `ACCEPT`/`MODIFY`/`REJECT` decision are externally verifiable under the selected trust profile and bound to the exact request, review material and draft.
5. Only an exact final-live-verified, fresh, non-replayed `ACCEPT` whose exact provider snapshot is successfully globally consumed as `CONTRACT_ACCEPT` can create `AUTHORIZED_AND_FROZEN`. Before that cutoff, edit/delete/mismatch/expiry/revocation blocks. Failed global consumption creates no authority and retry requires new final live verification. After successful `CONTRACT_ACCEPT`, later source-provider mutation does not retroactively revoke or alter the frozen contract.
6. The solution proposal/plan is produced by the selected intelligence boundary without the user supplying the code fix and without giving the proposer effect authority.
7. The consequential action is authorized against the exact current frozen contract, policy, input commit, path and before/after content; authorization is atomically consumed once and its terminal result is durably bound.
8. Execution is isolated, bounded and fail-closed. The target failure is reproduced before mutation; target and required regressions pass after mutation; protected material and scope are verified.
9. The result is a reviewable patch or draft PR as required by the selected endpoint, with no auto-merge, and a concise truthful report ending only in `ACTION_COMPLETED_REVIEW_REQUIRED`, `BLOCKED` or `FAILED`.
10. Evidence is bound to the exact code/input/environment and can be replayed or independently checked without the executor process's memory or self-report.
11. Documentation, implementation inventory, commands, support limits and maturity claims match actual `main`; no known contradictory success claim remains.
12. All required tests, adversarial gates, package/CLI smoke checks and relevant CI pass at the exact candidate SHA; non-gating diagnostic workflows are removed, disabled or explicitly separated from release status.
13. No active critical-path branch, PR, temporary issue or undocumented blocker remains. Historical evidence is preserved without presenting abandoned drafts as active work.
14. The branch-specific endpoint gates in section 4.2 pass.
15. A fresh independent Phase-C verifier returns `PROJECT COMPLETION: PASS` and the human makes the final acceptance decision required by the selected endpoint.

### 4.2 Completion endpoint alternatives (`HR-1`)

These are the historical Phase-A alternatives. `HR-1 C — P4 Repeatable Executor 1.0` is selected for Phase B.

#### A — Bounded Executor v1 functional slice

Additional DONE conditions:

- the complete normal-request-to-review path works for the exact controlled GP001 fixture;
- verified human authority, freeze, solution proposal, atomic authorization consumption and independent evidence all work in that bounded scope;
- the claim is explicitly `BOUNDED V1 FUNCTIONAL SLICE`, not real-value MVP, repeatability, production readiness or Executor 1.0.

Consequence: shortest route and strongest isolation, but it proves architecture/function rather than value on a real user problem.

#### B — P3 Real Value MVP

Additional DONE conditions are every P3 gate from `EXECUTOR_PRODUCT_CAPABILITY_LADDER.md`:

- one authorized real repository and exact commit;
- one real bounded problem affecting 1–3 files;
- no manual solution edit;
- draft PR and regression evidence;
- human reviewer accepts the patch as sensible;
- review takes less human work than manual implementation;
- cost and run reproducibility are recorded;
- final human product decision is `CONTINUE`, `REWORK` or `STOP`; only `CONTINUE/ACCEPT` can support project completion.

Consequence: proves first real product value, but not repeatability or a 1.0 release.

#### C — P4 Repeatable Executor 1.0

Additional DONE conditions are every P3 gate plus every P4 gate:

- a frozen supported class of small tasks;
- multiple real runs across more than one repository or independent module set;
- measured success/review acceptance rate, cost, latency and human time;
- known failure taxonomy and honest bounded retry;
- stable operator workflow and version/model regression policy;
- documented limits and comparison with manual execution;
- explicit human `EXECUTOR 1.0: ACCEPT` decision and a release/tag if separately authorized.

Consequence: best matches a repeatable “whole product 1.0” claim, but requires materially more external pilots, time, cost and human review than A or B.

## 5. Complete gap map

| ID | Material gap | Depends on | Decision owner | DONE WHEN |
|---|---|---|---|---|
| GAP-01 | `RESOLVED` — terminal completion level | none | `HUMAN` (`HR-1`) | `C — P4 Repeatable Executor 1.0` selected in `PHASE_B_AUTHORIZATION.md` |
| GAP-02 | `RESOLVED` — trusted front-door placement | GAP-01 | `HUMAN` (`HR-2`) | `A — external governed request intake` selected |
| GAP-03 | `RESOLVED FOR CURRENT PILOT` — trust provider/profile and authority semantics | GAP-02 | `HUMAN` (`HR-3`) | GitHub + `trust_profiles/github-p4-pilots.json` selected; revocation cutoff refined by the 2026-08-17 human decision |
| GAP-04 | Canonical docs/state contradict merged implementation and current owner | GAP-01–03 for semantic wording | mixed: human approves semantics; implementation is `AI_DELEGABLE` | authoritative docs agree with exact `main`, current owner and selected DONE |
| GAP-05 | Normal request surface is not on `main` | GAP-04 only for final wording | `AI_DELEGABLE` | bounded CLI/API passes happy and fail-closed paths; PR #59 is merged, revised or replaced on current base |
| GAP-06 | Verified `ACCEPT/MODIFY/REJECT` consumption and freeze do not exist | GAP-02–03, GAP-05 | implementation `AI_DELEGABLE` within approved trust contract | exact fresh decision creates only the legal state; attacks fail closed |
| GAP-07 | AAP atomic consumption/result binding is absent; GP001 uses a run-local set | GAP-06 before real consequential execution | `AI_DELEGABLE` unless changing AAP semantics | concurrent/replayed/crashed execution yields exactly one durable consumption and one bound terminal result |
| GAP-08 | No selected source of a non-human-written solution proposal is connected | GAP-01; semantic ownership in `HR-4` | `HUMAN_REQUIRED` for ownership/provider authority, then `AI_DELEGABLE` | an approved proposal boundary supplies a bounded candidate without effect authority and without hard-coded solution evidence |
| GAP-09 | Request formation, freeze, solver proposal, authority and GP001 are not orchestrated end to end | GAP-05–08 | `AI_DELEGABLE` | one operator path reaches review-required or honest blocked/failed from a normal request |
| GAP-10 | Current runtime only supports one exact controlled fixture and creates no user draft PR | GAP-01, GAP-09, `HR-5` | human grants external authority; implementation `AI_DELEGABLE` | endpoint-specific source acquisition, output commit/patch/draft PR and policy binding pass |
| GAP-11 | Independent evidence/replay does not cover the full request-to-result chain | GAP-06–10 | `AI_DELEGABLE` | fresh verifier can validate origin, decision, freeze, proposal, effect, result and report from durable artifacts |
| GAP-12 | Product-value/repeatability evidence is absent | GAP-09–11 | external inputs/human review required; run execution `AI_DELEGABLE` | A, B or C endpoint metrics and acceptance gates pass |
| GAP-13 | CI contains historical diagnostic workflows and a known noisy failure | may start after map approval | `AI_DELEGABLE` for repo cleanup; workflow-policy changes follow project approval rules | required checks are explicit and green; obsolete diagnostics no longer signal project failure |
| GAP-14 | 62 branches, 17 draft PRs and temporary issue #35 obscure active state | GAP-01–03 before closing semantic drafts | `AI_DELEGABLE` after preserving decisions/evidence | one active completion path remains; obsolete/temp items are closed with provenance pointers; retention policy is documented |
| GAP-15 | Release/operator documentation and packaging evidence are incomplete | GAP-09–12 | `AI_DELEGABLE`; public release is human-authorized | setup/use/error/report docs match reality; wheel/CLI smoke passes; support/version policy matches endpoint |
| GAP-16 | Final independent completion fact and human acceptance do not exist | GAP-01–15 | independent verifier + `HUMAN_REQUIRED` acceptance | Phase C returns PASS and final human decision is recorded |

## 6. Dependency constraints and provisional completion path

The arrows below express hard prerequisites and currently known constraint relationships. They are not a fixed execution schedule. Subject to those prerequisites, each next action is selected by the adaptive completion-control rule in section 0.1.

```text
HISTORICAL PHASE-A DEPENDENCY BASELINE: main@728d23e / P0 + bounded GP001 + formation phase 1
  |
  +--> HR-1 SELECT COMPLETION ENDPOINT (A / B / C)
  +--> HR-2 SELECT TRUSTED FRONT-DOOR PLACEMENT
  +--> HR-3 SELECT TRUST PROVIDER / EVIDENCE DOMAIN
  +--> HR-4 SELECT SOLUTION-INTELLIGENCE OWNERSHIP
  +--> HR-5 AUTHORIZE ENDPOINT-SPECIFIC EXTERNAL EFFECTS / PILOTS
          |
          v
  CANONICALIZE STATE + INTEGRATE/REPLACE PR #59
          |
          v
  VERIFIED ORIGIN + DECISION VERIFIER
          |
          v
  EXACT ACCEPT/MODIFY/REJECT -> FREEZE
          |
          +------------------------+
          |                        |
          v                        v
  SOLUTION PROPOSAL BOUNDARY   ATOMIC AAP LEDGER + RESULT BINDING
          |                        |
          +------------+-----------+
                       v
            REQUEST-TO-RESULT ORCHESTRATION
                       |
                       v
          ENDPOINT A FIXTURE | B REAL PILOT | C PILOT SERIES
                       |
                       v
            FULL EVIDENCE + METRICS + CLEANUP
                       |
                       v
             INDEPENDENT PHASE-C VERIFICATION
                       |
                       v
                FINAL HUMAN ACCEPTANCE
```

Parallel work is permitted only where the arrows allow it. In particular, solver-interface work and the atomic ledger may proceed in parallel after their semantic contracts are fixed; no real effect may run before verified freeze and atomic effect authority exist. After either path changes project state materially, the whole project is reassessed before more work is selected.

## 7. Decision forks

### 7.1 `HUMAN_REQUIRED`

#### HR-1 — What terminal claim completes Executor?

| Option | Meaning | Enables | Sacrifices / risk |
|---|---|---|---|
| A | bounded Executor v1 functional slice | shortest closed E2E proof on GP001 fixture | no real-value, repeatability or 1.0 claim |
| B | P3 Real Value MVP | proves one real problem is worth delegating | no repeatability; needs real repo, review and measured human-time reduction |
| C | P4 Repeatable Executor 1.0 | supports a whole-product 1.0 claim | largest evidence burden, multiple pilots, stable operations and model/version policy |

#### HR-2 — Where does trusted request origin begin?

| Option | Meaning | Enables | Sacrifices / risk |
|---|---|---|---|
| A | A1: externalized governed request intake | simpler trust topology; origin and decision share one external transaction domain | changes the governed product front door from direct Executor intake to an external authority domain |
| B | strengthened A2: Executor front door plus direct external origin attestation before formation | preserves direct `USER -> EXECUTOR` experience | requires a new pre-formation verified request envelope/boundary; later authentication alone is insufficient |
| C | retain unverified request intake and stop at non-executable phase 1 | preserves current low-risk demonstrator | cannot satisfy the accepted executable v1 promise, P3 or P4; requires explicit scope reduction |

Naive A2 (“accept local request now, authenticate later”) is already rejected by the draft adversarial analysis because `USER provenance != VERIFIED REQUEST-ORIGIN EVIDENCE`.

#### HR-3 — Which external trust/evidence domain is canonical?

| Option | Meaning | Enables | Sacrifices / risk |
|---|---|---|---|
| A | external transaction/approval platform owns request plus decision events | strong event IDs, actor provenance and approval lifecycle in one domain | vendor/workflow coupling; must prove direct-principal action and immutable event revision |
| B | external identity root plus human signing/approval ceremony over exact request/draft hashes | provider-independent artifact verification and direct exact-content binding | key/device lifecycle, revocation and user ceremony complexity |
| C | enterprise IdP/workflow authority service | organizational governance and delegated operational fit | changes target operating context, adds IAM/legal/admin dependencies and may not fit an individual-user product |

The human must name the concrete provider/profile, not only the class, before implementation can claim real authority.

#### HR-4 — Who owns solution generation?

| Option | Meaning | Enables | Sacrifices / risk |
|---|---|---|---|
| A | External Intelligence supplies a proposal through a frozen interface; Executor only governs effects; Saddle may validate intent conformity but does not select/author the solution path | preserves semantic ownership and provider independence | requires a stable cross-system proposal/evidence contract and integration environment |
| B | an Executor-System cognitive adapter calls one selected model/provider | self-contained first product experience | adds provider credentials, spend, model-version policy and cognitive responsibility inside this product system |
| C | deterministic pre-authored transformations only | no model cost or provider dependency | remains a controlled transformation demo; cannot prove “sensible fix without human supplying solution” for a real problem |

#### HR-5 — What real-world effect authority is granted?

| Option | Meaning | Enables | Sacrifices / risk |
|---|---|---|---|
| A | controlled fixture only, no GitHub write | endpoint A | cannot pass P3/P4 |
| B | one named real pilot repository/task, exact commit, draft PR only | endpoint B and the first P3 proof | needs repository authorization, GitHub write capability and human review; still no merge |
| C | frozen supported task/repository class with bounded draft-PR authority | endpoint C and P4 series | broader policy, operations and failure surface; requires evidence before generalization |

Exact repository, task, budget, credentials, retention and legal/commercial constraints are part of this human decision.

#### HR-6 — Final acceptance and release

Only the human may:

- accept the selected product/maturity claim;
- authorize merge of semantic completion state if not otherwise delegated;
- authorize a public release/tag;
- authorize deployment, paid spend, new secrets or broader repository effects.

### 7.2 `AI_DELEGABLE`

After HR-1–HR-5 are fixed and full Phase-B delegation is explicit, the agent may decide and record rationale for:

- whether to merge, revise, cherry-pick or replace PR #59's implementation;
- module boundaries, APIs, schemas and internal data structures that preserve the approved contracts;
- implementation sequencing within section 6;
- deterministic validation and error-handling design;
- local persistence technology for atomic consumption/result binding when it creates no new external commitment;
- test fixtures, adversarial cases and CI job structure;
- minimal dependency choices justified by a measured need;
- refactoring required to remove duplication or connect the accepted path;
- exact retry limits within the approved budget and semantics;
- documentation reconciliation and release-note wording that does not change the claim;
- closure/deletion of obsolete branches, PRs, issue #35 and diagnostic workflows after preserving necessary evidence;
- abandoning a failed implementation branch and choosing another reversible approach;
- stopping unnecessary work once every selected DONE gate is objectively satisfied.

The agent must escalate only a newly discovered fork that changes product meaning, external authority, legal/commercial commitment, accepted risk or the DONE definition.

## 8. Possible external blockers

These are possible Phase-B blockers, not current blockers to completing Phase A:

1. No human selection of HR-1–HR-5.
2. No accessible trust provider capable of proving request origin and exact direct-principal decisions with required freshness/revocation semantics.
3. Missing provider configuration, signing keys, webhooks or secrets after the provider is selected.
4. No authorized real pilot repository/problem for endpoint B or C.
5. No GitHub write permission to create a draft PR in the selected pilot repository.
6. No approved model/provider credential or budget if HR-4 option B is selected.
7. Docker/hosted-runner outage or inability to obtain immutable sandbox images and exact external source commits.
8. External provider/API changes that invalidate the approved trust or worker profile.
9. No independent fresh-session/model verifier for Phase C.
10. No human reviewer to judge real patch usefulness, time reduction and final product acceptance.

A normal engineering difficulty, failed first approach, stale branch, test failure or documentation contradiction is not an external blocker.

## 9. Final PASS gates

At the exact completion candidate SHA, every applicable gate must be recorded as `PASS` with locators:

| Gate | Required evidence |
|---|---|
| G-01 Goal/endpoint | recorded human approval of goal, DONE endpoint and HR choices |
| G-02 Canonical truth | automated/manual document-state audit finds no material contradiction |
| G-03 Request origin | forged, substituted, retroactive and wrong-subject origin evidence blocks |
| G-04 Decision/freeze | only exact final-live-verified ACCEPT may create CONTRACT_ACCEPT; pre-cutoff edit/delete/mismatch/expiry/replay blocks; the exact snapshot becomes immutable authority only after successful global CONTRACT_ACCEPT consumption/result binding; failed consumption creates no freeze and retry re-verifies live state; post-cutoff source mutation does not retroactively revoke the frozen contract; snapshot substitution/replay remains fail-closed |
| G-05 Solver separation | solution is not hand-authored by user and proposer has no effect authority |
| G-06 Atomic authority | concurrent attempts produce exactly one consumption and one result binding; crash recovery is fail-closed |
| G-07 Input identity | repository, commit, source tree, workflow and sandbox image match exact approved identities |
| G-08 Precondition | target failure or other real acceptance counterexample is reproduced before change |
| G-09 Postcondition | target and required regressions pass after change |
| G-10 Scope | allowed paths only; protected tests/material unchanged unless explicitly authorized |
| G-11 Isolation | no host fallback, worker network/secrets only as approved, resource limits and cleanup pass |
| G-12 Report | result is truthful, concise and limited to review-required/blocked/failed |
| G-13 Replay | independent replay/check validates complete origin-to-result evidence without process memory |
| G-14 CI/package | unit, integration/Docker, compile, validators, wheel install/CLI smoke and required workflows pass |
| G-15 Endpoint value | all branch-specific A, B or C gates in section 4.2 pass |
| G-16 Repository closure | no unfinished critical-path PR/branch/temp issue; obsolete evidence work is clearly archived/closed |
| G-17 Independent verdict | fresh Phase-C verifier returns `PROJECT COMPLETION: PASS` |
| G-18 Human acceptance | explicit final acceptance for the selected claim; release only if separately authorized |

Any unmet applicable gate yields `BLOCKED` or `FALSE-COMPLETION`, never a weaker interpretation of DONE.

## 10. Independent completion verification plan

A fresh session/model that did not execute Phase B receives only:

- canonical target repository state at the candidate SHA;
- this map as approved by the human;
- the recorded HR decisions and completion authorization;
- durable evidence generated during Phase B.

It performs the following independently:

1. Pin repository, branch, commit, tree, open PR/issue inventory and workflow definitions.
2. Verify that the accepted goal/DONE and all HR decisions are present and unchanged.
3. Reconstruct the real entrypoints/call graph for request, origin verification, formation, freeze, solution proposal, action authority, runtime, evidence and reporting.
4. Run full unit discovery, compile, project/task/test validators, package build/install and CLI smoke in a fresh environment.
5. Run Docker/security/integration tests with immutable image identity and verify cleanup.
6. Execute a fresh happy-path case permitted by the selected endpoint without reusing Phase-B process memory.
7. Execute the negative matrix: forged origin, wrong actor, mutable/rebound event, model-generated ACCEPT, draft mismatch, MODIFY/REJECT, expired/revoked/replayed decision, proposal scope drift, stale source, wrong commit, protected-path edit, packet race/replay, crash between consumption and result, tampered evidence and false-success report.
8. Recompute hashes and replay/verify durable evidence from raw artifacts rather than trusting the executing agent's summary.
9. For endpoint B/C, inspect the real patch/draft PR and human review/time/cost measurements; for C, recompute the series metrics and failure taxonomy.
10. Check documentation and all open branches/PRs/issues for goal drift or unfinished critical-path work.
11. Check that no Saddle repository content was modified by Executor completion work.
12. Return exactly one verdict:

```text
PROJECT COMPLETION: PASS
PROJECT COMPLETION: BLOCKED
PROJECT COMPLETION: FALSE-COMPLETION
```

The executing agent's own DONE statement is observational evidence only and cannot satisfy G-17.

## 11. Phase-B execution package after human approval

The approved Phase-B agent should begin from fresh `main`, not by merging a historical stack. It may mine old drafts for requirements and tests, but every adopted change must be reconciled with the current code and selected HR decisions.

Coverage obligations, not a fixed workflow:

1. canonical state/docs and CI hygiene;
2. current request surface;
3. selected origin/decision trust adapter and verifier;
4. exact decision-to-freeze transition;
5. atomic AAP consumption and result binding;
6. selected solution-proposal interface/adapter;
7. request-to-result orchestration;
8. endpoint-specific fixture/real-pilot execution and draft-PR output;
9. full evidence/replay, metrics and documentation;
10. independent Phase-C handoff.

The agent may reorder, combine, replace or eliminate workstreams when evidence shows that another available capability reaches the unchanged DONE more directly. After every material state change it must rerun the whole-project constraint assessment from section 0.1. Phase B ends only at G-01–G-18 PASS or an objective external blocker.

## 12. Human semantic approval template

The protocol's one semantic gate can be recorded using this complete shape:

```text
RECOVERED EXECUTOR GOAL: ACCEPT / CORRECT AS FOLLOWS: ...
DEFINITION OF DONE ENDPOINT (HR-1): A / B / C
TRUSTED FRONT DOOR (HR-2): A / B / C
TRUST PROVIDER / PROFILE (HR-3): [concrete provider/domain + required evidence rules]
SOLUTION OWNERSHIP (HR-4): A / B / C
REAL-WORLD EFFECT AUTHORITY (HR-5): A / B / C + exact repo/task/budget/credential bounds
AI_DELEGABLE DECISIONS: DELEGATED WITHIN THE APPROVED MAP
CONTINUATION: AUTHORIZED UNTIL ALL SELECTED DONE GATES PASS OR AN OBJECTIVE EXTERNAL BLOCKER OCCURS
MERGE / RELEASE / DEPLOY AUTHORITY: [state explicitly]
```

This gate was subsequently supplied in `PHASE_B_AUTHORIZATION.md`. The current state is:

```text
PHASE B AUTHORIZED WITHIN RECORDED BOUNDARIES
P4 NOT CLAIMED
FINAL HUMAN ACCEPTANCE NOT RECORDED
```


## 13. G-04 revocation-cutoff clarification — HUMAN DECISION (2026-08-17)

This section records and governs the revocation meaning used by section 4.1(5) and gate G-04. The human explicitly accepted:

```text
AKCEPTUJĘ REVOCATION CUTOFF AT GLOBAL CONTRACT_ACCEPT CONSUMPTION
AKCEPTUJĘ FINAL LIVE VERIFICATION AS REVOCATION CUTOFF BOUND INTO SUCCESSFUL GLOBAL CONTRACT_ACCEPT CONSUMPTION
```

Normative linearization:

```text
MUTABLE REQUEST / ACCEPT
  -> FINAL LIVE PROVIDER VERIFICATION
  -> EXACT IMMUTABLE SNAPSHOT S
  -> GLOBAL CONTRACT_ACCEPT(SHA256(S))
  -> if successful and durably bound: AUTHORIZED_AND_FROZEN(S)
```

Before final live verification, mutable-provider edit/deletion/mismatch/expiry is revocation and must block. If final verification produces `S` but global `CONTRACT_ACCEPT` fails, `S` is not authority and may not become authority later; retry requires a new final live provider verification. If exact `S` is successfully consumed and frozen, a provider mutation after the final verification does not retroactively revoke `S`, including mutation occurring after the verification read but before successful global consumption; the accepted cutoff is the final verification snapshot conditional on successful consumption. GitHub cross-resource atomicity is not claimed.

After successful freeze, consequential EFFECT authorization remains a separate gate and must use the immutable frozen snapshot + successful `CONTRACT_ACCEPT` receipt together with all existing AAP, policy, provider-time, local-consumption, scope, isolation and result-binding controls. Mutable source GitHub state must not silently become a post-cutoff revocation mechanism.
