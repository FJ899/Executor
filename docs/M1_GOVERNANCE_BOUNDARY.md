# M1 governance boundary

The structural validators answer whether a dictionary has the expected shape. They do not prove that a task is ready to execute.

Authoritative validation additionally requires:

- the exact `EXECUTOR_POLICY.yaml` supplied by the caller and matching the repository file;
- executor policy precedence over project and task capability requests;
- existing, regular and contained project entrypoint and authoritative source files;
- concrete repository commit locks;
- a concrete SHA-256 lock for the referenced test contract and a matching file;
- deterministic policy/verifier evidence for `HARD_VETO` rather than a model's own assertion.

The example `GINSENG_TEST-003` task intentionally remains blocked because it still contains `LOCKED_SHA` and `LOCKED_HASH`. A separate `EXECUTOR_TASK_FIXTURE-001` exists only to prove the validator's positive path.

This boundary does not yet solve repository-path canonicalization, symlink-aware task scopes or production loading of wrapped repository content. Those are kept for the next focused M1 change.
