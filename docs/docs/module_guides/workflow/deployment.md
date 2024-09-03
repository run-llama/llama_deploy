# 🦙 `llama_deploy` 🤖

`llama_deploy` (formerly `llama-agents`) is an async-first framework for deploying, scaling, and productionizing agentic multi-service systems based on [workflows from `llama_index`](https://docs.llamaindex.ai/en/stable/understanding/workflows/). With `llama_deploy`, you can build any number of workflows in `llama_index` and then bring them into `llama_deploy` for deployment.

In `llama_deploy`, each workflow is seen as a `service`, endlessly processing incoming tasks. Each workflow pulls and publishes messages to and from a `message queue`.

At the top of a `llama_deploy` system is the `control plane`. The control plane handles ongoing tasks, manages state, keeps track of which services are in the network, and also decides which service should handle the next step of a task using an `orchestrator`. The default `orchestrator` is purely programmatic, handling failures, retries, and state-passing.

The overall system layout is pictured below.

![A basic system in llama_deploy](./system_diagram.png)

## Why `llama_deploy`?

1. **Seamless Deployment**: It bridges the gap between development and production, allowing you to deploy `llama_index` workflows with minimal changes to your code.

2. **Scalability**: The microservices architecture enables easy scaling of individual components as your system grows.

3. **Flexibility**: By using a hub-and-spoke architecture, you can easily swap out components (like message queues) or add new services without disrupting the entire system.

4. **Fault Tolerance**: With built-in retry mechanisms and failure handling, `llama_deploy` ensures robustness in production environments.

5. **State Management**: The control plane manages state across services, simplifying complex multi-step processes.

6. **Async-First**: Designed for high-concurrency scenarios, making it suitable for real-time and high-throughput applications.

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
client = LlamaDeployClient(ControlPlaneConfig())

session = client.create_session()
result = session.run("my_workflow", arg1="hello_world")
print(result)
# prints 'hello_world_result'
```

### Deploying Nested Workflows

Every `Workflow` is capable of injecting and running nested workflows. For example

```python
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step


class InnerWorkflow(Workflow):
    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        arg1 = ev.get("arg1")
        if not arg1:
            raise ValueError("arg1 is required.")

        return StopEvent(result=str(arg1) + "_result")


class OuterWorkflow(Workflow):
    @step()
    async def run_step(
        self, ev: StartEvent, inner: InnerWorkflow
    ) -> StopEvent:
        arg1 = ev.get("arg1")
        if not arg1:
            raise ValueError("arg1 is required.")

        arg1 = await inner.run(arg1=arg1)

        return StopEvent(result=str(arg1) + "_result")


inner = InnerWorkflow()
outer = OuterWorkflow()
outer.add_workflows(inner=InnerWorkflow())
```

`llama_deploy` makes it dead simple to spin up each workflow above as a service, and run everything without any changes to your code!

Just deploy each workflow:

> [!NOTE]
> This code is launching both workflows from the same script, but these could easily be separate scripts, machines, or docker containers!

```python
import asyncio
from llama_deploy import (
    WorkflowServiceConfig,
    ControlPlaneConfig,
    deploy_workflow,
)


async def main():
    inner_task = asyncio.create_task(
        deploy_workflow(
            inner,
            WorkflowServiceConfig(
                host="127.0.0.1", port=8003, service_name="inner"
            ),
            ControlPlaneConfig(),
        )
    )

    outer_task = asyncio.create_task(
        deploy_workflow(
            outer,
            WorkflowServiceConfig(
                host="127.0.0.1", port=8002, service_name="outer"
            ),
            ControlPlaneConfig(),
        )
    )

    await asyncio.gather(inner_task, outer_task)


if name == "main":
    import asyncio

    asyncio.run(main())
```

And then use it as before:

```python
from llama_deploy import LlamaDeployClient

# points to deployed control plane
client = LlamaDeployClient(ControlPlaneConfig())

session = client.create_session()
result = session.run("outer", arg1="hello_world")
print(result)
# prints 'hello_world_result_result'
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
) -> None:
    control_plane_url = control_plane_config.url

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{control_plane_url}/queue_config")
        queue_config_dict = response.json()

    message_queue_config = _get_message_queue_config(queue_config_dict)
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

## Using the `llama_deploy` client

`llama_deploy` provides both a synchronous and an asynchronous client for interacting with a deployed system.

Both clients have the same interface, but the asynchronous client is recommended for production use to enable concurrent operations.

Generally, there is a top-level client for interacting with the control plane, and a session client for interacting with a specific session. The session client is created automatically for you by the top-level client and returned from specific methods.

To create a client, you need to point it to a control plane.

```python
from llama_deploy import (
    LlamaDeployClient,
    AsyncLlamaDeployClient,
    ControlPlaneConfig,
)

client = LlamaDeployClient(ControlPlaneConfig())
async_client = AsyncLlamaDeployClient(ControlPlaneConfig())
```

### Client Methods

- `client.create_session(poll_interval=DEFAULT_POLL_INTERVAL)`: Creates a new session for running workflows and returns a SessionClient for it. A session encapsulates the context and state for a single workflow run.
  Example:

  ```python
  session = client.create_session()
  ```

- `client.list_sessions()`: Lists all sessions registered with the control plane.
  Example:

  ```python
  sessions = client.list_sessions()
  for session in sessions:
      print(session.session_id)
  ```

- `client.get_session(session_id, poll_interval=DEFAULT_POLL_INTERVAL)`: Gets an existing session by ID and returns a SessionClient for it.
  Example:

  ```python
  session = client.get_session("session_123")
  ```

- `client.get_or_create_session(session_id, poll_interval=DEFAULT_POLL_INTERVAL)`: Gets an existing session by ID, or creates a new one if it doesn't exist.
  Example:

  ```python
  session = client.get_or_create_session("session_123")
  ```

- `client.get_service(service_name)`: Gets the definition of a service by name.
  Example:

  ```python
  service = client.get_service("my_workflow")
  print(service.service_name, service.host, service.port)
  ```

- `client.delete_session(session_id)`: Deletes a session by ID.
  Example:

  ```python
  client.delete_session("session_123")
  ```

- `client.list_services()`: Lists all services registered with the control plane.
  Example:

  ```python
  services = client.list_services()
  for service in services:
      print(service.service_name)
  ```

- `client.register_service(service_def)`: Registers a service with the control plane.
  Example:

  ```python
  service_def = ServiceDefinition(
      service_name="my_workflow", host="localhost", port=8000
  )
  client.register_service(service_def)
  ```

- `client.deregister_service(service_name)`: Deregisters a service from the control plane.
  Example:
  ```python
  client.deregister_service("my_workflow")
  ```

### SessionClient Methods

- `session.run(service_name, **run_kwargs)`: Implements the workflow-based run API for a session.
  Example:

  ```python
  result = session.run("my_workflow", arg1="hello", arg2="world")
  print(result)
  ```

- `session.create_task(task_def)`: Creates a new task in the session.
  Example:

  ```python
  task_def = TaskDefinition(input='{"arg1": "hello"}', agent_id="my_workflow")
  task_id = session.create_task(task_def)
  ```

- `session.get_tasks()`: Gets all tasks in the session.
  Example:

  ```python
  tasks = session.get_tasks()
  for task in tasks:
      print(task.task_id, task.status)
  ```

- `session.get_current_task()`: Gets the current (most recent) task in the session.
  Example:

  ```python
  current_task = session.get_current_task()
  if current_task:
      print(current_task.task_id, current_task.status)
  ```

- `session.get_task_result(task_id)`: Gets the result of a task in the session if it has one.
  Example:
  ```python
  result = session.get_task_result("task_123")
  if result:
      print(result.result)
  ```
