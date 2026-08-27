---
document: "SOLUTION_PROVIDER_001_P4_FINDING_11_REMEDIATION"
version: "1.0"
status: "P3 REMEDIATION CANDIDATE"
date: "2026-08-27"
scope: "P4 finding #11 — caller-controlled generation-verifier trust root"
repository: "FJ899/Executor"
parent_stage2_head: "54f754a36c18e9f230154210d8f3763a71507be9"
---

# P4 finding #11 — runtime verifier trust boundary

## Finding preserved

Independent P4 found that Stage 2 head `54f754a36c18e9f230154210d8f3763a71507be9`
allowed an effect-capable `PilotRuntime` caller to supply the same
`SolutionGenerationVerifier` that established provider evidence.

Because `SolutionGenerationVerifier` is a Python protocol and
`VerifiedGenerationEvidence` is ordinary caller-constructible data, a caller
could construct a matching verifier/evidence pair. Exact field equality,
response reconstruction, challenge binding, and terminal freeze-receipt
binding do not create an independent trust root when the resolver itself is
caller-controlled.

This finding remains valid for the historical audited head. CI success and the
GP001 Stage-2-only proof do not overwrite it.

## Remediation rule

Stage 2 has no provider-backed runtime trust anchor. Therefore it must not
pretend that a caller-supplied verifier is trusted.

For the Stage 2 boundary:

```text
AUTHORIZED_AND_FROZEN
        |
        v
SolutionProvider
        |
        v
ValidatedSolutionProposal
        |
        v
EFFECT_CAPABILITY = NONE
```

Mechanical generation-evidence resolution remains useful as zero-effect
validation evidence, but it is not runtime/effect authority.

`PilotRuntime` must fail closed before policy loading or any effect whenever a
caller attempts to supply a solution-generation verifier. With no
provider-backed trusted runtime resolver installed, the runtime is also not
eligible to consume a Stage 2 proposal merely because the proposal and a
caller-controlled evidence record are mutually consistent.

The exact adversarial case that must stay blocked is:

```text
caller-created structural proposal
+ caller-created SolutionGenerationVerifier
+ caller-created matching VerifiedGenerationEvidence
        |
        v
PilotRuntime
        |
        v
BLOCK BEFORE POLICY / SANDBOX / AUTHORITY / EFFECT
```

## What this remediation does not do

It does not add:

- a provider network client;
- credentials or secrets;
- a cryptographic signing service;
- a new runtime capability;
- branch/commit/push/PR publication;
- merge, release, deploy, or tag;
- Stage 3 capability.

A future layer that wants to re-enable effect-capable consumption must install
a real provider-backed trust root whose identity/provenance is not supplied by
the proposal caller, and that new boundary requires fresh independent P4.

## Epistemic status

A `ValidatedSolutionProposal` remains a Stage 2 result, not execution
authority. Mechanical provider-evidence re-resolution is evidence about
consistency; it is not proof that the resolver itself is trusted.

This amendment supersedes any wording in `SOLUTION_PROVIDER_001.md` that says
supplying a `SolutionGenerationVerifier` is sufficient to cross the runtime
boundary. Until a real trusted runtime resolver exists, caller-supplied
verifiers are forbidden and runtime consumption remains fail-closed.
