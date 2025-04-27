# Contributing to llama_deploy

Thank you for your interest in contributing to llama_deploy! This document provides guidelines and
instructions for contributing to the project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/llama_deploy.git`
3. Set up your development environment (see below)
4. Create a feature branch: `git checkout -b feature/my-feature`

## Development Environment

### Installing uv

We use `uv` for package management. If you don't have it installed:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or on macOS with Homebrew:
```
brew install uv
```

For more installation options, visit the [uv documentation](https://docs.astral.sh/uv/getting-started/installation/).

### Setting up the project

Run the unit tests to verify your setup:
```
uv run -- pytest tests
```

You can also run the end-to-end tests:
```
uv run -- pytest e2e_tests
```

## Making Changes

1. Make your changes
2. Add or update tests as needed
3. Run tests to make sure everything passes
4. Update documentation if necessary
5. Commit your changes with a descriptive message

## Pull Request Process

1. Push changes to your fork
2. Submit a pull request to the main repository
3. Add a clear description of the changes
4. Address any review comments

## Code Style

Follow the existing code style in the project. We use:

- Black for code formatting
- Ruff for linting

## Testing

- Write tests for any new functionality
- Ensure all tests pass before submitting a PR
- Run tests with: `uv run -- pytest`

## Documentation

- Update documentation for any changed functionality
- Document new features thoroughly

## Questions?

If you have questions about contributing, please open an issue in the repository.

Thank you for contributing to llama_deploy!
