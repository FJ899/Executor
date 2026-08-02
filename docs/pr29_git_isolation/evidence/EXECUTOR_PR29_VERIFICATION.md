# Executor PR #29 - targeted verification

## Scope

- Public PR state and changed-file scope checked against the supplied review protocol.
- Current head reviewed: `514ba20d67bd415e438440c62f47307709177a7f`.
- Current GitHub Actions run reviewed: `30766241419`.
- A local adversarial reproduction was executed against the exact Git safety switches used in `executor/pilot_core.py::git_command`.

## Formal result

- PR: open draft
- Base: `main`
- Head branch: `agent/pilot-runtime-replacement`
- Commits: 1
- Changed files: 21, matching the expected list
- GitHub Actions: `foundation-tests` and `sandbox-security` succeeded

## Adversarial test

The reproduction kept the tracked source checkout clean and at the same commit, while adding only untracked Git metadata:

- `.git/info/attributes` assigns a filter to `project_registry/registry.py`;
- `.git/config` defines executable `smudge` and `clean` filter commands.

The test then ran the same overrides used by Executor:

```text
-c core.hooksPath=/dev/null
-c core.fsmonitor=false
-c core.attributesFile=/dev/null
-c core.autocrlf=false
-c commit.gpgSign=false
```

Observed result:

```text
smudge_via_git_info_attributes=EXECUTED
clean_via_git_info_attributes=EXECUTED
source_status_before=
source_status_after=
```

Therefore host-side code execution is still possible during `git worktree add` and `git add`, despite the source being clean and pinned.

## Decision

`REWORK`

Reason: the mandatory Git-isolation property is not satisfied. The current regression test covers an executable `post-checkout` hook, but not clean/smudge filters loaded from repository-local Git metadata. This is a narrow, fixable security defect and does not require stopping the entire pilot.

## Minimum remediation

1. Run Git operations with a fully isolated configuration, not merely `GIT_CONFIG_NOSYSTEM=1` and selected `-c` overrides.
2. Disable or reject all clean/smudge/process filters for host-side checkout and staging operations.
3. Add negative tests using `.git/info/attributes` plus local `filter.<name>.smudge`, `clean`, and `process` commands.
4. Repeat full CI and the entire review on the new head SHA.
