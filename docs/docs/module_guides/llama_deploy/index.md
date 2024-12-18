# 🦙 LlamaDeploy 🤖

LlamaDeploy (formerly `llama-agents`) is an async-first framework for deploying, scaling, and productionizing agentic
multi-service systems based on [workflows from `llama_index`](https://docs.llamaindex.ai/en/stable/understanding/workflows/).
With LlamaDeploy, you can build any number of workflows in `llama_index` and then run them as services, accessible
through a HTTP API by a user interface or other services part of your system.

The goal of LlamaDeploy is to easily transition something that you built in a notebook to something running on the
cloud with the minimum amount of changes to the original code, possibly zero. In order to make this transition a
pleasant one, the intrinsic complexity of running agents as services is managed by a component called
[_API Server_](./20_core_components.md#api-server), the only one in LlamaDeploy that's user facing. You can interact
with the API Server in two ways:

- Using the [`llamactl`](50_llamactl.md) CLI from a shell.
- Through the [_LlamaDeploy SDK_](40_python_sdk.md) from a Python application or script.

Both the SDK and the CLI are distributed with the LlamaDeploy Python package, so batteries are included.

The overall system layout is pictured below.

![A basic system in llama_deploy](https://github.com/run-llama/llama_deploy/blob/5e7703e98faa8d682a679832872094258a172629/system_diagram.png?raw=true)

## Why LlamaDeploy?

1. **Seamless Deployment**: It bridges the gap between development and production, allowing you to deploy `llama_index`
   workflows with minimal changes to your code.
2. **Scalability**: The microservices architecture enables easy scaling of individual components as your system grows.
3. **Flexibility**: By using a hub-and-spoke architecture, you can easily swap out components (like message queues) or
   add new services without disrupting the entire system.
4. **Fault Tolerance**: With built-in retry mechanisms and failure handling, LlamaDeploy adds robustness in
   production environments.
5. **State Management**: The control plane manages state across services, simplifying complex multi-step processes.
6. **Async-First**: Designed for high-concurrency scenarios, making it suitable for real-time and high-throughput
   applications.

## Wait, where is `llama-agents`?

The introduction of [Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/#workflows) in `llama_index`
turned out to be the most intuitive way for our users to develop agentic applications. While we keep building more and
more features to support agentic applications into `llama_index`, LlamaDeploy focuses on closing the gap between local
development and remote execution of agents as services.

## Installation

`llama_deploy` can be installed with pip, and includes the API Server Python SDK and `llamactl`:

```bash
pip install llama_deploy
```
