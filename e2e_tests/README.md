# E2E Tests

E2E tests are run in the `e2e-tests` workflow in `.github/workflows/e2e-tests.yml`.

They are written such that a `run.sh` script can be executed to run some number of tests locally.

Each folder in this directory represents a set of tests for simple scenarios.

When new folders are added, they will be executed automatically in the CI/CD pipeline, assuming the `run.sh` script runs successfully.
