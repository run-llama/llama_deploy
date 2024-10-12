# 🦙 Llama Deploy 🤖

Llama Deploy (formerly `llama-agents`) is an async-first framework for deploying, scaling, and productionizing agentic
multi-service systems based on [workflows from `llama_index`](https://docs.llamaindex.ai/en/stable/understanding/workflows/).
With Llama Deploy, you can build any number of workflows in `llama_index` and then run them as services, accessible
through a HTTP API by a user interface or other services part of your system.

In Llama Deploy each workflow is wrapped in a _Service_ object, endlessly processing incoming requests in form of
_Task_ objects. Each service pulls and publishes messages to and from a _Message Queue_. An internal component called
_Control Plane_ handles ongoing tasks, manages the internal state, keeps track of which services are available, and
decides which service should handle the next step of a task using another internal component called _Orchestrator_.
A well defined set of these components is called _Deployment_, and a single Llama Deploy instance can serve multiple
of them.

The goal of Llama Deploy is to easily transition something that you built in a notebook to something running on the
cloud with the minimum amount of changes to the original code, possibly zero. In order to make this transition a
pleasant one, the intrinsic complexity of running agents as services is managed by a component called _API Server_,
the only one in Llama Deploy that's user facing. You can interact with the API Server in two ways:

- Using the `llamactl` CLI from a shell.
- Through the _LLama Deploy SDK_ from a Python application or script.

Both the SDK and the CLI are distributed with the Llama Deploy Python package, so batteries are included.

The overall system layout is pictured below.

![A basic system in llama_deploy](./system_diagram.png)

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

## Wait, where is `llama-agents`?

The introduction of [Workflows](https://docs.llamaindex.ai/en/stable/module_guides/workflow/#workflows) in `llama_index`
turned out to be the most intuitive way for our users to develop agentic applications. While we keep building more and
more features to support agentic applications into `llama_index`, Llama Deploy focuses on closing the gap between local
development and remote execution of agents as services.

## Installation

`llama_deploy` can be installed with pip, and includes the API Server Python SDK and `llamactl`:

```bash
pip install llama_deploy
```

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

> [!TIP]
> By default, CORS is enabled. If you want to disable it, you can set the `DISABLE_CORS` environment variable:
> ```
> $ DISABLE_CORS=true python -m llama_deploy.apiserver
> ```

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

## Manual deployment without the API server

Llama Deploy offers different abstraction layers for maximum flexibility. For example, if you don't need the API
server, you can go down one layer and orchestrate the core components on your own. Llama Deploy provides a simple way
to self-manage a deployment using configuration objects and helper functions.

### Deploying the Core System

> [!NOTE]
> When manually orchestrating a deployment, generally you'll want to deploy the core components and workflows services
> each from their own python scripts (or docker images, etc.).

To manually orchestrate a deployment, the first thing to do is to deploy the core system: message queue, control plane,
and orchestrator. You can use the `deploy_core` function:

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


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

This will set up the basic infrastructure for your deployment. You can customize the configs to adjust ports and basic
settings, as well as swap in different message queue configs (Redis, Kafka, RabbiMQ, etc.).

### Deploying a Workflow

To deploy a workflow as a service, you can use the `deploy_workflow` function:

```python
from llama_deploy import (
    deploy_workflow,
    WorkflowServiceConfig,
    ControlPlaneConfig,
    SimpleMessageQueueConfig,
)
from llama_index.core.workflow import (
    Context,
    Event,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)


class ProgressEvent(Event):
    progress: str


# create a dummy workflow
class MyWorkflow(Workflow):
    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        # Your workflow logic here
        arg1 = str(ev.get("arg1", ""))
        result = arg1 + "_result"

        # stream events as steps run
        ctx.write_event_to_stream(
            ProgressEvent(progress="I am doing something!")
        )

        return StopEvent(result=result)


async def main():
    await deploy_workflow(
        workflow=MyWorkflow(),
        workflow_config=WorkflowServiceConfig(
            host="127.0.0.1", port=8002, service_name="my_workflow"
        ),
        control_plane_config=ControlPlaneConfig(),
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
```

This will deploy your workflow as a service and register it with the existing control plane and message queue.

### Interacting with your Deployment

Once deployed, you can interact with your deployment using a client.

```python
from llama_deploy import LlamaDeployClient, ControlPlaneConfig

# points to deployed control plane
client = LlamaDeployClient(ControlPlaneConfig())

session = client.create_session()
result = session.run("my_workflow", arg1="hello_world")
print(result)
# prints 'hello_world_result'
```

If you want to see the event stream as well, you can do:

```python
# create a session
session = client.create_session()

# kick off run
task_id = session.run_nowait("streaming_workflow", arg1="hello_world")

# stream events -- the will yield a dict representing each event
for event in session.get_task_result_stream(task_id):
    print(event)

# get final result
result = session.get_task_result(task_id)
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

Llama Deploy makes it dead simple to spin up each workflow above as a service, and run everything without any changes
to your code!

Just deploy each workflow:

> [!NOTE]
> This code is launching both workflows from the same script, but these could easily be separate scripts, machines,
> or docker containers!

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


if __name__ == "__main__":
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

## Manual deployment using the lower level API

For more control over the deployment process, you can use the lower-level API. Here's what's happening under the hood
when you use `deploy_core` and `deploy_workflow`:

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

## Using the Python SDK

Llama Deploy provides access to a deployed system through a synchronous and an asynchronous client. Both clients have
the same interface, but the asynchronous client is recommended for production use to enable concurrent operations.

Generally, there is a top-level client for interacting with the control plane, and a session client for interacting
with a specific session. The session client is created automatically for you by the top-level client and returned from
specific methods.

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

## Message Queue Integrations

In addition to `SimpleMessageQueue`, we provide integrations for various
message queue providers, such as RabbitMQ, Redis, etc. The general usage pattern
for any of these message queues is the same as that for `SimpleMessageQueue`,
however the appropriate extra would need to be installed along with `llama-deploy`.

For example, for `RabbitMQMessageQueue`, we need to install the "rabbitmq" extra:

```sh
# using pip install
pip install llama-agents[rabbitmq]

# using poetry
poetry add llama-agents -E "rabbitmq"
```

Using the `RabbitMQMessageQueue` is then done as follows:

```python
from llama_agents.message_queue.rabbitmq import (
    RabbitMQMessageQueueConfig,
    RabbitMQMessageQueue,
)

message_queue_config = (
    RabbitMQMessageQueueConfig()
)  # loads params from environment vars
message_queue = RabbitMQMessageQueue(**message_queue_config)
```

<!-- prettier-ignore-start -->
> [!NOTE]
> `RabbitMQMessageQueueConfig` can load its params from environment variables.
<!-- prettier-ignore-end -->
