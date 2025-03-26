# Core Components

LlamaDeploy consists of several core components acting as services in order to provide the environment where
multi-agent applications can run and communicate with each other. This sections details each and every component and
will help you navigate the rest of the documentation.

## Deployment

In LlamaDeploy each workflow is wrapped in a [_Service_](#service) object, endlessly processing incoming requests in
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

For more details, see the API reference for the deployment [`Config`](../../api_reference/llama_deploy/apiserver.md#llama_deploy.apiserver.deployment_config_parser.DeploymentConfig) object.

## API Server

The API Server is a core component of LlamaDeploy responsible for serving and managing multiple deployments at the same time,
and it exposes a HTTP API that can be used for administrative purposes as well as for querying the deployed services.
You can interact with the administrative API through [`llamactl`](./50_llamactl.md) or the [Python SDK](./40_python_sdk.md).

For more details see [the Python API reference](../../api_reference/llama_deploy/apiserver.md), while the administrative
API is documented below.

!!swagger apiserver.json!!

## Control Plane

The control plane is responsible for managing the state of the system, including:

- Registering services.
- Managing sessions and tasks.
- Handling service completion.
- Launching the control plane server.

The state of the system is persisted in a key-value store that by default consists of a simple mapping in memory.
In particular, the state store contains:

- The name and definition of the registered services.
- The active sessions and their relative tasks and event streams.
- The Context, in case the service is of type Workflow,

In case you need a more scalable storage for the system state, you can set the `state_store_uri` field in the Control
Plane configuration to point to one of the databases we support (see
[the Python API reference](../../api_reference/llama_deploy/control_plane.md)) for more details.
Using a scalable storage for the global state is mostly needed when:
- You want to scale the control plane horizontally, and you want every instance to share the same global state.
- The control plane has to deal with high traffic (many services, sessions and tasks).
- The global state needs to be persisted across restarts (for example, workflow contexts are stored in the global state).

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

### Delivery policy

Currently the way service replicas receive the message to run a task depends on
the message queue implementation:

- `SimpleMessageQueue`: consumers are competing but the order is non
deterministic, the first subscriber (in this case, the first service) that
manages to get the message in the topic wins, all the others will keep trying
and never know a message was published.
- `RedisMessageQueue`: by default, all the services get the message and run the
task. If you set the `exclusive_mode` configuration parameter of the
`RedisMessageQueueConfig` class to `True`, services will compete for messages
and only the first coming will be able to read it.
- `RabbitMQMessageQueue`: consumers are competing, a round robin policy is used
to pick the recipient
- `KafkaMessageQueue`: same as RabbitMQ because the `group_id` of the consumer
is hardcoded
- `AWSMessageQueue`: technically similar to Redis, but the consumer removes the
message from the queue so it's actually non-deterministic.


## Orchestrator

The general idea for an orchestrator is to manage the flow of messages between services.

Given some state, and task, figure out the next messages to publish. Then, once
the messages are processed, update the state with the results.

## Task

A Task is an object representing a request for an operation sent to a Service and the response that will be sent back.
For the details you can look at the [API reference](../../api_reference/llama_deploy/types.md)
