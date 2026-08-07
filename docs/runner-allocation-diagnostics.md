# Runner allocation diagnostics

This repository contains a small set of GitHub Actions workflow files for verifying runner allocation behavior on GitHub-hosted runners.

## Workflow files

- [.github/workflows/diagnostic.yml](../.github/workflows/diagnostic.yml): minimal smoke test that prints `runner-ok`.
- [.github/workflows/runner-allocation-heavy-test.yml](../.github/workflows/runner-allocation-heavy-test.yml): single long-running job to check whether a heavy job still receives a runner.
- [.github/workflows/runner-allocation-competition-test.yml](../.github/workflows/runner-allocation-competition-test.yml): two parallel jobs to test runner competition and queueing behavior.

## How to use

1. Open the Actions tab in GitHub.
2. Select one of the workflows above.
3. Run it manually from the branch you want to test.
4. Review the job logs to see whether the runner was assigned and how queueing behaved.
