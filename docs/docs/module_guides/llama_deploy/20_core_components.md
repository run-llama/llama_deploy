# Core Components

Llama Deploy consists of several core components acting as services in order to provide the environment where
multi-agent applications can run and communicate with each other. This sections details each and every component and
will help you navigate the rest of the documentation.

## Deployment

In Llama Deploy each workflow is wrapped in a [_Service_](#service) object, endlessly processing incoming requests in
form of [_Task_](#task) objects. Each service pulls and publishes messages to and from a [_Message Queue_](#message-queue).
An internal component called [_Control Plane_](#control-plane) handles ongoing tasks, manages the internal state, keeps
track of which services are available, and decides which service should handle the next step of a task using another
internal component called [_Orchestrator_](#orchestrator).

A well defined set of these components is called _Deployment_.

Deployments can be defined with YAML code, for example:

```yaml
name: QuickStart

control-plane:
  port: 8000

default-service: dummy_workflow

services:
  dummy_workflow:
    name: Dummy Workflow
    source:
      type: local
      name: src
    path: workflow:echo_workflow
```

For more details, see the API reference for the deployment [`Config`](../../api_reference/llama_deploy/apiserver.md#llama_deploy.apiserver.config_parser.Config) object.

## API Server

The API Server is a core component of Llama Deploy responsible for serving and managing multiple deployments. It is
responsible for running and managing multiple deployments at the same time, and it exposes a HTTP API that can be used
for administrative purposes as well as for querying the deployed services. You can interact with the administrative
API through [`llamactl`](./50_llamactl.md) or the [Python SDK](./40_python_sdk.md).

For more details see [the Python API reference](../../api_reference/llama_deploy/apiserver.md), while the administrative
API is documented below.

!!swagger apiserver.json!!

## Control Plane

The control plane is responsible for managing the state of the system, including:

- Registering services.
- Managing sessions and tasks.
- Handling service completion.
- Launching the control plane server.

## Service

The general structure of a service is as follows:

- A service has a name.
- A service has a service definition.
- A service uses a message queue to send/receive messages.
- A service has a processing loop, for continuous processing of messages.
- A service can process a message.
- A service can publish a message to another service.
- A service can be launched in-process.
- A service can be launched as a server.
- A service can be registered to the control plane.
- A service can be registered to the message queue.

## Message Queue

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


> [!NOTE]
> `RabbitMQMessageQueueConfig` can load its params from environment variables.


## Orchestrator

The general idea for an orchestrator is to manage the flow of messages between services.

Given some state, and task, figure out the next messages to publish. Then, once
the messages are processed, update the state with the results.

## Task

A Task is an object representing a request for an operation sent to a Service and the response that will be sent back.
For the details you can look at the [API reference](../../api_reference/llama_deploy/types.md)
