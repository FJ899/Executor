# Validation truth boundary

The Executor distinguishes three separate claims:

1. **Structural validity** — a dictionary has the expected fields and value types.
2. **Authoritative validation** — policy, files, repository locks, hashes, holdout evidence and other external facts were actually checked.
3. **Execution readiness** — authoritative validation completed with status `VALID`.

A structurally valid project or task is not ready for a model. Structural validators therefore return:

- `status: VALID` when the shape is valid;
- `authoritative: false`;
- `ready_for_model: false`;
- `execution_status: BLOCKED_BEFORE_MODEL`.

Only authoritative bundle validators and the evidence-backed test validator can return `READY_FOR_MODEL`.

All contract files are loaded with strict JSON rules. Duplicate object keys and `NaN`, `Infinity` or `-Infinity` are rejected regardless of whether the caller uses the CLI or the Python API.

Evidence paths use the same repository-grade boundary as production repository reads: normalized relative POSIX paths, no symlink component, no hardlinks, regular files and containment within the supplied base directory. This applies to source claims, holdouts, project entrypoints, authoritative sources and locked test contracts.
