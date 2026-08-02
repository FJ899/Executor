# M2B execution boundary

Docker isolation is not an authorization mechanism. The backend must know which repository and commit it is about to mount before it invokes Docker.

Each execution therefore requires a `SandboxExecutionContext` containing:

- repository identity;
- exact commit;
- verified repository root;
- source directory contained in that root;
- an explicit purpose: `EXECUTOR_FIXTURE` or `PROJECT`.

With `EXECUTOR_POLICY.yaml execution.external_projects=false`, only `EXECUTOR_FIXTURE` executions from `litrgratis-pixel/Executor` are allowed. The gate runs before Docker preflight or container creation. Enabling external projects later requires an explicit policy change and still requires a verified GitHub checkout and exact `HEAD`.

The source directory is checked lexically before symlink resolution and physically afterwards. This prevents a symlink in any parent component from disappearing during `resolve()`.

Cleanup is verified independently of `docker rm` and independently of the wording of `docker inspect` errors. After removal, the backend requires a successful `docker ps -a` query filtered to the exact container name. Only return code 0 and an empty result prove absence. Daemon errors, timeouts, an unexpected name or a still-visible container are fail-closed and make the sandbox result unsuccessful.
