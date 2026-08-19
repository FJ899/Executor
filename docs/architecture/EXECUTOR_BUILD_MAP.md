---
document: "Executor Build Map"
version: "1.2"
status: "OWNERSHIP RECONCILIATION CANDIDATE / EXISTING PRODUCT STATE UNCHANGED"
date: "2026-08-19"
scope: "canonical architectural decomposition of Executor System"
repository: "JTJ07/Executor"
---

# Executor Build Map v1.2

## 1. Purpose

This map answers:

> What are we actually building?

It is an architecture map, not a maturity certificate and not an implementation inventory.

Three separate questions remain separate:

- **Build Map** — what belongs to the system;
- **Implementation Inventory** — what currently exists;
- **Maturity / Proof Ladder** — what has been proven.

`HUMAN_AI_DELIBERATION_MODEL.md` is a cross-cutting way of working and is not a separate maturity axis.

Semantic ownership is also separate from technical hosting. A single model/process may technically perform several steps, but competence or co-location does not transfer ownership between Human, Intelligence, Contract Formation, Executor or Verifier.

## LEVEL 0 — PRODUCT DEFINITION

Executor is a system. The execution kernel is one component of that system. Contract Formation is a governed boundary inside the system, but operational HOW remains owned by External/Base Intelligence.

```text
HUMAN REQUEST / ACCEPTED MEANING
      |
      v
EXTERNAL / BASE INTELLIGENCE
 interpret problem / propose or select HOW
      |
      v
CONTRACT FORMATION
 materialize / bind / provenance-check / critique for drift
      |
      v
DRAFT TASK CONTRACT
      |
      v
HUMAN AUTHORIZATION
      |
      v
FROZEN TASK CONTRACT
      |
      v
EXECUTOR KERNEL
      |
      +--> plans execution inside the frozen solution boundary
      +--> executes
      +--> observes
      +--> produces technical evidence
      |
      v
INDEPENDENT VERIFIER
 establishes facts
```

Core definition:

> Executor System materializes a bounded proposal into an explicit, reviewable contract surface, requires authority before that proposal becomes executable, then executes the frozen contract within policy and produces observable evidence for independent verification and review.

Executor/Contract Formation does not:

- own the user's goal;
- own operational HOW merely because it can process or generate text;
- treat AI/Intelligence interpretation as authoritative user intent;
- silently convert a draft into execution authority;
- change user intent;
- create its own project canon;
- make strategic/normative decisions on behalf of the user;
- treat its own claim of success as authoritative proof.

## LEVEL 1 — FOUNDATION

### F0. Request / Proposal-to-Contract Boundary

Defines and enforces the transition:

```text
REQUEST / ACCEPTED MEANING
  -> INTELLIGENCE PROPOSAL
  -> MATERIALIZED DRAFT CONTRACT
  -> HUMAN AUTHORIZATION
  -> FROZEN CONTRACT
```

Formation is governed. No non-authorized formation state may enter the execution kernel.

The semantic ownership split is explicit:

```text
INTELLIGENCE
  proposes/selects HOW and candidate contract meaning

CONTRACT FORMATION
  materializes/binds supplied meaning, preserves provenance,
  validates compatibility and rejects scope/authority drift
```

Formation must not originate, rank, select, route or optimize operational HOW.

### F1. Contract Interpretation Boundary

The execution kernel receives project/task contracts, constraints, acceptance criteria and authority. It does not override them.

Before authorization, Contract Formation may materialize fields supplied by Intelligence and may critique them for structural/provenance/scope problems. The kernel executes only the frozen contract.

If the proposal itself must change, that is a return to Intelligence and, where normative meaning changes, to the Human — not autonomous contract-layer solution selection.

### F2. Source & Workspace Access

Includes:

- repository access;
- source acquisition;
- pinned input identity;
- workspace lifecycle;
- controlled inputs.

### F3. Execution State Model

Executor needs explicit formation and execution lifecycles, including bounded transitions, blocked/failed outcomes and replay/revalidation behavior.

Formation state and execution state must not be collapsed into one implicit model state.

### F4. Evidence Boundary

Executor records actions, artifacts and observable technical results. Execution evidence is not the same as Human acceptance, product truth or strategic lineage.

Independent verification owns the factual verdict over the evidence; Executor does not gain final-verifier ownership by producing or checking technical observations during execution.

## LEVEL 2 — CORE STRUCTURE

### S0. Contract Formation Flow

```text
Intelligence Proposal / Accepted Meaning
      |
      v
Materialize Draft
      |
      v
Bind Provenance + Exact Inputs
      |
      v
Critique for Drift / Unsupported Inference
      |
      v
Present Decision Surface
      |
      v
Human Authorization
      |
      v
Frozen Task Contract
```

Question answered:

> Can the supplied proposal be represented as an exact, reviewable action boundary without adding meaning, scope or authority?

Not:

> Which operational solution should be selected?

Not:

> What should the user's goal really be?

### S1. Runtime Engine

```text
Frozen Task Contract
      |
      v
 Runtime Engine
      |
      +--> Plan execution inside accepted/frozen solution boundary
      +--> Execute
      +--> Observe
      +--> Record evidence
```

### S2. Execution Planning Layer

Question answered:

> How do we technically choreograph execution of the already approved/frozen solution?

Not:

> Which solution/HOW should the system choose?

Not:

> What should the user's goal really be?

Solution planning/selection belongs to Intelligence. Execution planning inside the accepted solution boundary may belong to Executor.

### S3. Action Execution Layer

Bounded operations such as:

- file operations;
- Git operations;
- commands;
- tests;
- explicitly authorized tools.

### S4. Evidence / Verification Handoff

```text
ACTION
  |
RESULT + RAW EVIDENCE
  |
  v
INDEPENDENT VERIFIER
  |
PASS / FAIL / BLOCKED FACTUAL VERDICT
```

Executor may perform internal technical checks needed to execute safely, but the independent verifier establishes the factual verdict used for higher-level closure. Verification may not grant product acceptance authority, retroactively authorize an action or convert technical success into Human acceptance.

## LEVEL 3 — EXECUTION INFRASTRUCTURE

### I1. Execution State & Working Memory

Executor may own:

- current formation/run state;
- checkpoints;
- execution artifacts;
- action results;
- data needed for replay and recovery.

Executor does not own:

- the user's strategic goal;
- strategic/normative decisions;
- operational HOW selection outside an already accepted solution boundary;
- project canon.

### I2. Context Management

Maintains the bounded working context needed to materialize or execute the current contract.

Formation context must distinguish user-supplied facts, accepted meaning and Intelligence/model inference. Storing or validating an inference does not make Contract Formation its semantic owner.

### I3. Tool Management

Controls tool exposure, constraints, credentials and execution conditions inside an authorized task.

Contract-formation tools may gather evidence needed to bind a proposal or validate its representation. They do not themselves choose operational HOW or grant execution authority.

### I4. Sandbox & Isolation

Provides controlled execution, separation, blast-radius limits and fail-closed behavior.

## LEVEL 4 — CAPABILITY MODULES

Capabilities reuse Executor Core. They are not separate Executors by default.

```text
                 EXECUTOR CORE
                      |
          +-----------+-----------+
          |           |           |
       SOFTWARE    ANALYSIS    RESEARCH
          |           |           |
          +-----------+-----------+
                      |
                   ACTIONS
```

### C1. Software Engineering Capability

Repository analysis, code change and tests inside the accepted task/solution boundary.

### C2. Analysis Capability

Structured data analysis, reports and bounded conclusions inside the accepted task/solution boundary.

### C3. Research Capability

Information collection, comparison and synthesis within an authorized task or an Intelligence/formation context.

Research may inform an Intelligence proposal or provide evidence for formation-time binding. Contract Formation may not silently convert research output into a newly selected HOW or broader executable authority.

### C4. Operational Capability

Repeatable procedures and bounded automation.

Capability does not imply authority or semantic ownership.

## LEVEL 5 — USER EXPERIENCE

### UX1. Request Surface

Possible surfaces include chat, web UI, API or CLI.

The product front door is the user's request, not an internal contract file format.

A first user should be able to say:

```text
Fix the failing test about batch atomicity.
```

without knowing how the internal task contract is encoded.

The system may use Intelligence to propose HOW and candidate meaning, but the user-facing product must preserve the distinction between that proposal and Human intent/authority.

### UX2. Contract Decision Surface

Before execution authority exists, expose only decision-relevant materialized contract information:

```text
REQUEST
PROPOSED / UNDERSTOOD OBJECTIVE
TARGET / INPUT IDENTITY
PROPOSED WRITE SCOPE
PROTECTED MATERIAL
SUCCESS CONDITIONS
DISCOVERED BUT OUT OF SCOPE
UNRESOLVED ASSUMPTIONS
PROVENANCE OF PROPOSED MEANING
STATUS: DRAFT — USER AUTHORIZATION REQUIRED
```

### UX3. Execution Interaction Model

After authorization, the user should receive decision-relevant execution information, not internal command noise.

Preferred shape:

```text
AUTHORIZED TASK
EXECUTION PLAN
CHANGED
EVIDENCE / VERIFICATION
LIMITATIONS / DISCOVERIES
STATUS
```

### UX4. Result Report

Every completed attempt ends with a truthful result that distinguishes execution, independent verification, limitations and the next Human decision.

## LEVEL 6 — EXTENSIONS

Possible later extensions include:

- capability marketplace;
- specialized role services;
- multi-agent deliberation;
- learning mechanisms;
- enterprise integrations.

These are not requirements for the first product slice.

## Cross-cutting rules

1. Human authority owns intent, semantic goals, DONE and normative decisions.
2. Ginseng may understand decision space but does not own operational HOW.
3. External/Base Intelligence proposes/selects operational HOW.
4. Contract Formation materializes/binds supplied or accepted meaning; it does not choose HOW or expand scope.
5. AI/Intelligence interpretation is not authoritative user intent.
6. Request is not contract.
7. Draft contract is not authorized contract.
8. Contract formation is a governed binding action.
9. Contract bounds execution.
10. Executor execution planning is technical choreography inside the accepted/frozen solution boundary, not solution selection.
11. Deliberation may improve recommendations but may not expand authority.
12. Capability is not authority and competence does not create semantic ownership.
13. Validated authority must still match current authority-critical state at consequential action time.
14. Executor result is not independent verifier fact; verifier fact is not Human acceptance.
15. Technical proof and product maturity remain separate from architectural existence.
16. A new component should remove a measured product or safety blocker, not merely add conceptual completeness.

## Reconciliation note

This v1.2 map removes the earlier visual ambiguity that placed `interpret / propose / critique` entirely inside `CONTRACT FORMATION` and could therefore be read as transferring HOW-selection ownership into the contract layer.

The reconciliation does not change Executor runtime, accepted Executor 1.0 completion, authority semantics, release/deploy state or product capability. It aligns the authoritative architecture map with the later accepted ecosystem ownership boundary and the already aligned implemented GP001 slice.
