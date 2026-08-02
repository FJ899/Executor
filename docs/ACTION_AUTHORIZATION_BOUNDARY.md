# Action authorization validation boundary

`validate_action_authorization_packet` validates eligibility for atomic consumption. It never reports that an action has already been executed.

The validator requires:

- exact immutable run, contract, policy and repository bindings;
- exact action kind, argv, paths and capabilities;
- policy-compatible network, secrets and external-project flags;
- externally verified evidence binding the issuer role and issuer ID;
- one-use integer constraint, bounded lifetime and canonical SHA-256 integrity;
- absence from the caller-supplied consumed packet set.

A packet that passes returns `READY_FOR_ATOMIC_CONSUMPTION`. It does not return `READY_FOR_MODEL` or `PASS`.

Atomic ledger consumption, race-safe replay prevention and binding the action result to the consumption event are M3 responsibilities. Until those exist, the validator is a frozen terminal contract and precondition, not an execution gate implementation.
