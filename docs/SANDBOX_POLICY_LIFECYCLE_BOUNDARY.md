# Sandbox policy and lifecycle boundary

The Docker backend does not accept a policy dictionary.

It requires an `ExecutionPolicySnapshot` loaded from `EXECUTOR_POLICY.yaml` in a verified `JTJ07/Executor` checkout. The file must match the blob at the exact checked-out commit. The snapshot records the policy SHA-256 and cannot be constructed through its public dataclass fields. The backend reloads and compares the snapshot before each authorization decision.

For Executor fixtures, the execution repository root and commit must be the same root and commit that produced the policy snapshot. For project execution, the snapshot must explicitly allow external projects.

The mounted source directory must exactly match the corresponding committed subtree:

- every committed file must exist;
- no additional tracked, untracked or ignored file may be present;
- every file must match its committed blob;
- symlinks, hardlinks and non-regular files are rejected.

Sandbox images must be immutable local image IDs in `sha256:<64 hex>` form.

Each container receives a random execution ID and reserved ownership label. The backend:

1. confirms the generated name is absent;
2. creates the container with ownership and policy-digest labels;
3. removes only a container whose ownership label matches;
4. independently proves absence with a successful exact `docker ps -a` query.

A create failure uses the same owned-cleanup path. An ownership mismatch, name collision, daemon failure or unverified absence is fail-closed. Error text such as `No such object` is not accepted as proof. The result records the execution ID and policy digest used for the run.
