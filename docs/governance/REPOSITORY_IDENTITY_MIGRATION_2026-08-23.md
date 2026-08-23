---
document: "Executor repository identity migration reconciliation"
status: "CURRENT REPOSITORY IDENTITY RECONCILIATION"
date: "2026-08-23"
current_repository: "FJ899/Executor"
pre_transfer_repository: "JTJ07/Executor"
base_main: "58876a9e0995c68234db9a0a61d146c90267895a"
---

# Executor repository identity migration — 2026-08-23

## Purpose

This record separates the repository transfer from historical provenance.

The live Executor repository is now:

```text
FJ899/Executor
```

The immediately pre-transfer repository identity was:

```text
JTJ07/Executor
```

## Current identity rule

Current runtime, validation, self-repository contracts, CI invocations and current navigation surfaces must bind to `FJ899/Executor`.

`JTJ07/Executor` must not remain an alternative current self identity. Strict repository verification is intentionally preserved: a checkout that resolves to the pre-transfer owner must not satisfy a current `FJ899/Executor` binding merely because GitHub can redirect old URLs.

## Historical provenance rule

The transfer does not rewrite facts that were originally bound to `JTJ07/Executor` at an exact historical SHA, run, decision or acceptance event.

In particular, dated evidence and the 2026-08-20 final Human acceptance record preserve their original `JTJ07/Executor` repository identity. Those records describe what was accepted or observed at that time; changing their repository field after the transfer would alter provenance.

```text
CURRENT REPOSITORY IDENTITY CHANGES
!=
HISTORICAL EVIDENCE IDENTITY CHANGES
```

## Non-target identities

This reconciliation does not rename independent repositories merely because they share an old owner namespace. Existing bindings such as `JTJ07/scriptops`, `JTJ07/creative-os-project-reconstructor`, `JTJ07/Saddle`, and `litrgratis-pixel/executor-pilot-target` are outside this migration unless separately transferred and reconciled.

## Regression boundary

`tests/test_repository_identity_migration.py` enforces both sides of the boundary:

1. active Executor self-bindings resolve to `FJ899/Executor`;
2. the dated Human acceptance record still resolves historically to `JTJ07/Executor`.

No merge, release, deploy, tag, product re-acceptance or rewriting of historical evidence is implied by this migration repair.
