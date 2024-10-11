[![PyPI - Version](https://img.shields.io/pypi/v/llama-deploy.svg)](https://pypi.org/project/llama-deploy)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/llama-deploy.svg)](https://pypi.org/project/llama-deploy)
[![Static Badge](https://img.shields.io/badge/docs-latest-blue)](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/)


[![Unit Testing](https://github.com/run-llama/llama_deploy/actions/workflows/unit_test.yml/badge.svg)](https://github.com/run-llama/llama_deploy/actions/workflows/unit_test.yml)
[![Coverage Status](https://coveralls.io/repos/github/run-llama/llama_deploy/badge.svg?branch=main)](https://coveralls.io/github/run-llama/llama_deploy?branch=main)


# 🦙 Llama Deploy 🤖

Llama Deploy (formerly `llama-agents`) is an async-first framework for deploying, scaling, and productionizing agentic
multi-service systems based on [workflows from `llama_index`](https://docs.llamaindex.ai/en/stable/understanding/workflows/).
With Llama Deploy, you can build any number of workflows in `llama_index` and then run them as services, accessible
through a HTTP API by a user interface or other services part of your system.

The goal of Llama Deploy is to easily transition something that you built in a notebook to something running on the
cloud with the minimum amount of changes to the original code, possibly zero. In order to make this transition a
pleasant one, you can interact with Llama Deploy in two ways:

- Using the [`llamactl`](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/50_llamactl/) CLI from a shell.
- Through the [_LLama Deploy SDK_](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/40_python_sdk/) from a Python application or script.

Both the SDK and the CLI are part of the Llama Deploy Python package. To install, just run:

```bash
pip install llama_deploy
```
> [!TIP]
> For a comprehensive guide to Llama Deploy's architecture and detailed descriptions of its components, visit our
[official documentation](https://docs.llamaindex.ai/en/latest/module_guides/llama_deploy/).

## Why Llama Deploy?

1. **Seamless Deployment**: It bridges the gap between development and production, allowing you to deploy `llama_index`
   workflows with minimal changes to your code.
2. **Scalability**: The microservices architecture enables easy scaling of individual components as your system grows.
3. **Flexibility**: By using a hub-and-spoke architecture, you can easily swap out components (like message queues) or
   add new services without disrupting the entire system.
4. **Fault Tolerance**: With built-in retry mechanisms and failure handling, Llama Deploy adds robustness in
   production environments.
5. **State Management**: The control plane manages state across services, simplifying complex multi-step processes.
6. **Async-First**: Designed for high-concurrency scenarios, making it suitable for real-time and high-throughput
   applications.

> [!NOTE]
> This project was initially released under the name `llama-agents`,  but the introduction of [Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/#workflows) in `llama_index` turned out to be the most intuitive way for our users to develop agentic applications. We then decided to add new agentic features in `llama_index` directly, and focus Llama Deploy on closing the gap between local development and remote execution of agents as services.

## Getting Started

Let's start with deploying a simple workflow on a local instance of Llama Deploy. After installing Llama Deploy, create
a `src` folder add a `workflow.py` file to it containing the following Python code:

```python
import asyncio
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step


class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        message = str(ev.get("message", ""))
        return StopEvent(result=f"Message received: {message}")


# `echo_workflow` will be imported by Llama Deploy
echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!"))


# Make this script runnable from the shell so we can test the workflow execution
if __name__ == "__main__":
    asyncio.run(main())
```

Test the workflow runs locally:

```
$ python src/workflow.py
Message received: Hello!
```

Time to deploy that workflow! Create a file called `deployment.yml` containing the following YAML code:

```yaml
name: QuickStart

control-plane:
  port: 8000

default-service: echo_workflow

services:
  echo_workflow:
    name: Echo Workflow
    # We tell Llama Deploy where to look for our workflow
    source:
      # In this case, we instruct Llama Deploy to look in the local filesystem
      type: local
      # The path in the local filesystem where to look. This assumes there's an src folder in the
      # current working directory containing the file workflow.py we created previously
      name: ./src
    # This assumes the file workflow.py contains a variable called `echo_workflow` containing our workflow instance
    path: workflow:echo_workflow
```

The YAML code above defines the deployment that Llama Deploy will create and run as a service. As you can
see, this deployment has a name, some configuration for the control plane and one service to wrap our workflow. The
service will look for a Python variable named `echo_workflow` in a Python module named `workflow` and run the workflow.

At this point we have all we need to run this deployment. Ideally, we would have the API server already running
somewhere in the cloud, but to get started let's start an instance locally. Run the following python script from a shell:

```
$ python -m llama_deploy.apiserver
INFO:     Started server process [10842]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4501 (Press CTRL+C to quit)
```

From another shell, use `llamactl` to create the deployment:

```
$ llamactl deploy deployment.yml
Deployment successful: QuickStart
```

Our workflow is now part of the `QuickStart` deployment and ready to serve requests! We can use `llamactl` to interact
with this deployment:

```
$ llamactl run --deployment QuickStart --arg message 'Hello from my shell!'
Message received: Hello from my shell!
```

### Run the API server with Docker

Llama Deploy comes with Docker images that can be used to run the API server without effort. In the previous example,
if you have Docker installed, you can replace running the API server locally with `python -m llama_deploy.apiserver`
with:

```
$ docker run -p 4501:4501 -v .:/opt/quickstart -w /opt/quickstart llamaindex/llama-deploy
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4501 (Press CTRL+C to quit)
```

The API server will be available at `http://localhost:4501` on your host, so `llamactl` will work the same as if you
run `python -m llama_deploy.apiserver`.

## Examples

This repository contains a few example applications you can use as a reference:

- [Quick start](examples/quick_start)
- [Deployment behind a web-based user interface](examples/python_fullstack)
- [Message queue examples](examples/message-queue-integrations)
