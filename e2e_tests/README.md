# E2E Tests

E2E tests are run in the `e2e-tests` workflow in `.github/workflows/e2e-tests.yml`.

Each folder in this directory contains a Python package representing a set of tests for a simple scenario.

When new folders are added, they will be executed automatically in the CI/CD pipeline by `pytest`.

To run all the tests:

```sh
$ uv run -- pytest -m"e2e"
```
or
```sh
$ uv run -- pytest ./e2e_tests
```

To run a specific scenario:

```sh
$ uv run -- pytest e2e_tests/basic_streaming
```

If you want to see the output of the different services running, pass the `-s` flag to pytest:

```sh
$ uv run -- pytest e2e_tests/basic_streaming -s
```
