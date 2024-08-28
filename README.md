# 🦙 `llama_deploy` 🤖

`llama_deploy` (formerly `llama-agents`) is an async-first framework for deploying, scaling, and productionizing agentic multi-service systems based on [workflows from `llama_index`](https://docs.llamaindex.ai/en/stable/understanding/workflows/). With `llama_deploy`, you can build any number of workflows in `llama_index` and then bring them into `llama_deploy` for deployment.

In `llama_deploy`, each workflow is seen as a `service`, endlessly processing incoming tasks. Each workflow pulls and publishes messages to and from a `message queue`.

At the top of a `llama_deploy` system is the `control plane`. The control plane handles ongoing tasks, manages state, keeps track of which services are in the network, and also decides which service should handle the next step of a task using an `orchestrator`. The default `orchestrator` is purely programmatic, handling failures, retries, and state-passing.

The overall system layout is pictured below.

![A basic system in llama_deploy](./system_diagram.png)

## Wait, where is `llama-agents`?

The introduction of [Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/#workflows) in `llama_index`produced the most intuitive way to develop agentic applications. The question then became: how can we close the gap between developing an agentic application as a workflow, and deploying it?

With `llama_deploy`, the goal is to make it as 1:1 as possible between something that you built in a notebook, and something running on the cloud in a cluster. `llama_deploy` enables this by simply being able to pass in and deploy any workflow.

## Installation

`llama_deploy` can be installed with pip, and relies mainly on `llama_index_core`:

```bash
pip install llama_deploy
```

## Getting Started

### High-Level Deployment

`llama_deploy` provides a simple way to deploy your workflows using configuration objects and helper functions.

When deploying, generally you'll want to deploy the core services and workflows each from their own python scripts (or docker images, etc.).

Here's how you can deploy a core system and a workflow:

### Deploying the Core System

To deploy the core system (message queue, control plane, and orchestrator), you can use the `deploy_core` function:

```python
from llama_deploy import (
    deploy_core,
    ControlPlaneConfig,
    SimpleMessageQueueConfig,
)


async def main():
    await deploy_core(
        control_plane_config=ControlPlaneConfig(),
        message_queue_config=SimpleMessageQueueConfig(),
    )


if name == "main":
    import asyncio

    asyncio.run(main())
```

This will set up the basic infrastructure for your `llama_deploy` system. You can customize the configs to adjust ports and basic settings, as well as swap in different message queue configs (Redis, Kafka, RabbiMQ, etc.).

### Deploying a Workflow

To deploy a workflow as a service, you can use the `deploy_workflow` function:

```python
python
from llama_deploy import (
    deploy_workflow,
    WorkflowServiceConfig,
    ControlPlaneConfig,
    SimpleMessageQueueConfig,
)
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step


# create a dummy workflow
class MyWorkflow(Workflow):
    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        # Your workflow logic here
        arg1 = str(ev.get("arg1", ""))
        result = arg1 + "_result"
        return StopEvent(result=result)


async def main():
    await deploy_workflow(
        workflow=MyWorkflow(),
        workflow_config=WorkflowServiceConfig(
            host="127.0.0.1", port=8002, service_name="my_workflow"
        ),
        control_plane_config=ControlPlaneConfig(),
        message_queue_config=SimpleMessageQueueConfig(),
    )


if name == "main":
    import asyncio

    asyncio.run(main())
```

This will deploy your workflow as a service within the `llama_deploy` system, and register the service with the existing control plane and message queue.

### Interacting with your Deployment

Once deployed, you can interact with your deployment using a client.

```python
from llama_deploy import LlamaDeployClient

# points to deployed control plane
client = LlamaAgentsClient(ControlPlaneConfig())

session = client.create_session()
result = session.run("my_workflow", arg1="hello_world")
print(result)
# prints 'hello_world_result'
```

## Components of a `llama_deploy` System

In `llama_deploy`, there are several key components that make up the overall system

- `message queue` -- the message queue acts as a queue for all services and the `control plane`. It has methods for publishing methods to named queues, and delegates messages to consumers.
- `control plane` -- the control plane is a the central gateway to the `llama_deploy` system. It keeps track of current tasks and the services that are registered to the system. The `control plane` also performs state and session management and utilizes the `orchestrator`.
- `orchestrator` -- The module handles incoming tasks and decides what service to send it to, as well as how to handle results from services. By default, the `orchestrator` is very simple, and assumes incoming tasks have a destination already specified. Beyond that, the default `orchestrator` handles retries, failures, and other nice-to-haves.
- `services` -- Services are where the actual work happens. A services accepts some incoming task and context, processes it, and publishes a result. When you deploy a workflow, it becomes a service.

## Low-Level Deployment

For more control over the deployment process, you can use the lower-level API. Here's what's happening under the hood when you use `deploy_core` and `deploy_workflow`:

### deploy_core

The `deploy_core` function sets up the message queue, control plane, and orchestrator. Here's what it does:

```python
async def deploy_core(
    control_plane_config: ControlPlaneConfig,
    message_queue_config: BaseSettings,
    orchestrator_config: Optional[SimpleOrchestratorConfig] = None,
) -> None:
    orchestrator_config = orchestrator_config or SimpleOrchestratorConfig()

    message_queue_client = _get_message_queue_client(message_queue_config)

    control_plane = ControlPlaneServer(
        message_queue_client,
        SimpleOrchestrator(**orchestrator_config.model_dump()),
        **control_plane_config.model_dump(),
    )

    message_queue_task = None
    if isinstance(message_queue_config, SimpleMessageQueueConfig):
        message_queue_task = _deploy_local_message_queue(message_queue_config)

    control_plane_task = asyncio.create_task(control_plane.launch_server())

    # let services spin up
    await asyncio.sleep(1)

    # register the control plane as a consumer
    control_plane_consumer_fn = await control_plane.register_to_message_queue()

    consumer_task = asyncio.create_task(control_plane_consumer_fn())

    # let things sync up
    await asyncio.sleep(1)

    # let things run
    if message_queue_task:
        all_tasks = [control_plane_task, consumer_task, message_queue_task]
    else:
        all_tasks = [control_plane_task, consumer_task]

    shutdown_handler = _get_shutdown_handler(all_tasks)
    loop = asyncio.get_event_loop()
    while loop.is_running():
        await asyncio.sleep(0.1)
        signal.signal(signal.SIGINT, shutdown_handler)

        for task in all_tasks:
            if task.done() and task.exception():  # type: ignore
                raise task.exception()  # type: ignore
```

This function:

1. Sets up the message queue client
2. Creates the control plane server
3. Launches the message queue (if using SimpleMessageQueue)
4. Launches the control plane server
5. Registers the control plane as a consumer
6. Sets up a shutdown handler and keeps the event loop running

### deploy_workflow

The `deploy_workflow` function deploys a workflow as a service. Here's what it does:

```python
async def deploy_workflow(
    workflow: Workflow,
    workflow_config: WorkflowServiceConfig,
    control_plane_config: ControlPlaneConfig,
    message_queue_config: BaseSettings,
) -> None:
    message_queue_client = _get_message_queue_client(message_queue_config)

    service = WorkflowService(
        workflow=workflow,
        message_queue=message_queue_client,
        **workflow_config.model_dump(),
    )

    service_task = asyncio.create_task(service.launch_server())

    # let service spin up
    await asyncio.sleep(1)

    # register to message queue
    consumer_fn = await service.register_to_message_queue()

    # register to control plane
    control_plane_url = (
        f"http://{control_plane_config.host}:{control_plane_config.port}"
    )
    await service.register_to_control_plane(control_plane_url)

    # create consumer task
    consumer_task = asyncio.create_task(consumer_fn())

    # let things sync up
    await asyncio.sleep(1)

    all_tasks = [consumer_task, service_task]

    shutdown_handler = _get_shutdown_handler(all_tasks)
    loop = asyncio.get_event_loop()
    while loop.is_running():
        await asyncio.sleep(0.1)
        signal.signal(signal.SIGINT, shutdown_handler)

        for task in all_tasks:
            if task.done() and task.exception():  # type: ignore
                raise task.exception()  # type: ignore
```

This function:

1. Sets up the message queue client
2. Creates a WorkflowService with the provided workflow
3. Launches the service server
4. Registers the service to the message queue
5. Registers the service to the control plane
6. Sets up a consumer task for the service
7. Sets up a shutdown handler and keeps the event loop running
