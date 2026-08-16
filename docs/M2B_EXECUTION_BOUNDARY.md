# M2B execution boundary

Docker isolation is not an authorization mechanism. The backend must know which repository and commit it is about to mount before it invokes Docker.

Each execution therefore requires a `SandboxExecutionContext` containing:

- repository identity;
- exact commit;
- verified repository root;
- source directory contained in that root;
- an explicit purpose: `EXECUTOR_FIXTURE` or `PROJECT`.

With `EXECUTOR_POLICY.yaml execution.external_projects=false`, generic external execution remains forbidden. The Phase B policy additionally permits only the two named `bounded_pilot_repositories`, with exact GitHub request/commit/tree authority and draft-PR-only output. The gate runs before Docker preflight or container creation.

The source directory is checked lexically before symlink resolution and physically afterwards. This prevents a symlink in any parent component from disappearing during `resolve()`.

Cleanup is verified independently of `docker rm` and independently of the wording of `docker inspect` errors. After removal, the backend requires a successful `docker ps -a` query filtered to the exact container name. Only return code 0 and an empty result prove absence. Daemon errors, timeouts, an unexpected name or a still-visible container are fail-closed and make the sandbox result unsuccessful.
