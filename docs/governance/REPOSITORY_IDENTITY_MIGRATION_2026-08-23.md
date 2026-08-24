---
document: "Executor repository identity migration reconciliation"
status: "CURRENT ECOSYSTEM REPOSITORY IDENTITY RECONCILIATION"
date: "2026-08-23"
current_repository: "FJ899/Executor"
pre_transfer_repository: "JTJ07/Executor"
base_main: "58876a9e0995c68234db9a0a61d146c90267895a"
---

# Executor repository identity migration — 2026-08-23

## Purpose

This record separates the live FJ899 namespace transfer from historical provenance.

The live Executor repository is now:

```text
FJ899/Executor
```

The immediately pre-transfer repository identity was:

```text
JTJ07/Executor
```

## Current identity rule

Current runtime, validation, self-repository contracts, CI invocations, trust profiles, controlled fixture bindings, bounded pilot bindings and current navigation surfaces must use the live FJ899 namespace.

For the repositories transferred in this ecosystem, current locators are:

```text
FJ899/Executor
FJ899/Saddle
FJ899/COS
FJ899/scriptops
FJ899/creative-os-project-reconstructor
FJ899/executor-pilot-target
```

Pre-transfer owner strings must not remain alternative current identities. Strict repository verification is intentionally preserved: a checkout or provider event using a pre-transfer locator must not satisfy a current FJ899 binding merely because GitHub can redirect old URLs.

## Historical provenance rule

The transfer does not rewrite facts that were originally bound to a pre-transfer repository identity at an exact historical SHA, run, request, decision or acceptance event.

In particular, dated evidence and the 2026-08-20 final Human acceptance record preserve their original `JTJ07/Executor` repository identity. The frozen 2026-08-16 P4 request evidence continues to verify against the preserved pre-transfer trust-profile snapshot in `trust_profiles/github-p4-pilots-pre-transfer-2026-08-16.json`.

```text
CURRENT REPOSITORY IDENTITY CHANGES
!=
HISTORICAL EVIDENCE IDENTITY CHANGES
```

## Current cross-repository bindings

The active Executor policy binds the transferred controlled fixture and bounded pilot repositories to their FJ899 locators:

```text
FJ899/executor-pilot-target
FJ899/scriptops
FJ899/creative-os-project-reconstructor
```

The active Human interaction pointer resolves current durable contract state from `FJ899/Saddle`.

These are live/current locators. Exact historical SHAs remain unchanged where they are evidence identities.

## Regression boundary

`tests/test_repository_identity_migration.py` enforces both sides of the boundary:

1. active Executor self-bindings resolve to `FJ899/Executor`;
2. active cross-repository policy/trust/pointer bindings use FJ899 locators;
3. the dated Human acceptance record still resolves historically to `JTJ07/Executor`;
4. frozen pre-transfer P4 request evidence keeps a separate preserved trust-profile identity.

No merge, release, deploy, tag, product re-acceptance or rewriting of historical evidence is implied by this migration repair.
