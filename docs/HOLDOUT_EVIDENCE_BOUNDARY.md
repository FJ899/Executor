# Holdout evidence boundary

A test contract can declare that a holdout should be hidden, but the declaration and a local file cannot prove that the implementer did not see it.

`validate_test_contract` therefore separates:

1. contract requirements (`HIDDEN_FROM_IMPLEMENTER`, `REPLAY_ONLY`, safe location);
2. artifact checks (regular file, contained path, non-empty, not a known placeholder, SHA-256 binding);
3. evidence supplied by a caller outside the test contract.

Without external holdout evidence, validation returns `INSUFFICIENT_EVIDENCE / HOLDOUT_VISIBILITY_UNVERIFIED`.

The evidence interface binds the test id, location, artifact hash, visibility and access claim. `TEST_FIXTURE_VERIFIER` is accepted only for contracts whose ids start with `EXECUTOR_VALIDATOR_FIXTURE-`; other tests require `INDEPENDENT_HOLDOUT_VERIFIER`.

This interface does not by itself provide cryptographic authenticity or an independent storage service. Those remain requirements for the later independent holdout design. Its purpose at M0 is narrower: prevent a self-declared local holdout from being reported as verified.
