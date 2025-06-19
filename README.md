[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![PyPI - Version](https://img.shields.io/pypi/v/llama-deploy.svg)](https://pypi.org/project/llama-deploy)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Frun-llama%2Fllama_deploy%2Frefs%2Fheads%2Fmain%2Fpyproject.toml)
[![Static Badge](https://img.shields.io/badge/docs-latest-blue)](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/)


[![Unit Testing](https://github.com/run-llama/llama_deploy/actions/workflows/unit_test.yml/badge.svg)](https://github.com/run-llama/llama_deploy/actions/workflows/unit_test.yml)
[![E2E Testing](https://github.com/run-llama/llama_deploy/actions/workflows/e2e_test.yml/badge.svg)](https://github.com/run-llama/llama_deploy/actions/workflows/e2e_test.yml)
[![Coverage Status](https://coveralls.io/repos/github/run-llama/llama_deploy/badge.svg?branch=main)](https://coveralls.io/github/run-llama/llama_deploy?branch=main)


# 🦙 LlamaDeploy 🤖

LlamaDeploy (formerly `llama-agents`) is an async-first framework for deploying, scaling, and productionizing agentic
multi-service systems based on [workflows from `llama_index`](https://docs.llamaindex.ai/en/stable/understanding/workflows/).
With LlamaDeploy, you can build any number of workflows in `llama_index` and then run them as services, accessible
through a HTTP API by a user interface or other services part of your system.

The goal of LlamaDeploy is to easily transition something that you built in a notebook to something running on the
cloud with the minimum amount of changes to the original code, possibly zero. In order to make this transition a
pleasant one, you can interact with LlamaDeploy in two ways:

- Using the [`llamactl`](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/40_llamactl/) CLI from a shell.
- Through the [_LlamaDeploy SDK_](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/30_python_sdk/) from a Python application or script.

Both the SDK and the CLI are part of the LlamaDeploy Python package. To install, just run:

```bash
pip install -U llama-deploy
```
> [!TIP]
> For a comprehensive guide to LlamaDeploy's architecture and detailed descriptions of its components, visit our
[official documentation](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/).

## Why LlamaDeploy?

1. **Seamless Deployment**: It bridges the gap between development and production, allowing you to deploy `llama_index`
   workflows with minimal changes to your code.
3. **Flexibility**: By using a hub-and-spoke architecture, you can easily swap out components (like message queues) or
   add new services without disrupting the entire system.
4. **Fault Tolerance**: With built-in retry mechanisms and failure handling, LlamaDeploy adds robustness in
   production environments.
6. **Async-First**: Designed for high-concurrency scenarios, making it suitable for real-time and high-throughput
   applications.

> [!NOTE]
> This project was initially released under the name `llama-agents`,  but the introduction of [Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/#workflows) in `llama_index` turned out to be the most intuitive way for our users to develop agentic applications. We then decided to add new agentic features in `llama_index` directly, and focus LlamaDeploy on closing the gap between local development and remote execution of agents as services.

## Quick Start with `llamactl`

Spin up a running deployment in minutes using the interactive CLI wizard:

```bash
# 1. Install the package & CLI
pip install -U llama-deploy

# 2. Scaffold a new project (interactive)
llamactl init

#    or non-interactive
llamactl init --name project-name --template basic

# 3. Enter the project
cd project-name

# 4. Start the control-plane API server (new terminal)
python -m llama_deploy.apiserver

# 5. Deploy the generated workflow (another terminal)
llamactl deploy deployment.yml

# 6. Call it!
llamactl run --deployment hello-deploy --arg message "Hello world!"
```

Looking for more templates or integrations? Check the [`examples`](examples) directory for end-to-end demos (message queues, web UIs, etc.) or read the full [documentation](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/).
