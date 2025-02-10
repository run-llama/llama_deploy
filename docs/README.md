# LlamaDeploy Documentation

This repository contains the documentation for LlamaDeploy, built using MkDocs with Material theme.

## Setup

### Prerequisites
- Python 3.10 or higher
- Poetry (for dependency management)

### Installation

1. Clone the repository
2. Install dependencies using Poetry:
```bash
poetry install
```

## Development

To start the documentation server locally:
```bash
poetry run mkdocs serve
```

This will start a development server at `http://127.0.0.1:8000`.

## Building

LlamaDeploy is part of LlamaIndex [documentation portal](https://docs.llamaindex.ai/)
so the build is performed from the [main repository](https://github.com/run-llama/llama_index).

> [!WARNING]
> When a documentation change is merged here, the change won't be visible until a new
> build is triggered from the LlamaIndex repository.


## Contributing

Contributions are very welcome!

1. Create a new branch for your changes
2. Make your changes to the documentation
3. Test locally using `poetry run mkdocs serve`
4. Submit a pull request
