# Example: Launching a Multi-Agent System with Docker and Kubernetes

In this example, we demonstrate how one can build a multi-agent app with a
structure and development flow more conducive to production. Specifically,
we employ a project structure that organizes the multi-agent app to its separate
components, namely:

- `core_services`: message queue and control plane
- `agent_services`: our agents and their respective services
- `additional_services`: additional services such as human consumer service or tool service

For more context, the contents of this example folder is provided below.

```sh
.
├── Makefile
├── README.md
├── docker-compose.yml
├── docker-example.ipynb
├── logging.ini
├── multi-agent-app
│   ├── Dockerfile
│   ├── README.md
│   ├── multi_agent_app
│   │   ├── __init__.py
│   │   ├── additional_services
│   │   ├── agent_services
│   │   ├── apps.py
│   │   ├── core_services
│   │   ├── local_launcher.py
│   │   └── utils.py
│   ├── poetry.lock
│   ├── pyproject.toml
│   ├── template.env.docker
│   └── template.env.local
└── task_results
    └── task_results.jsonl
```

## Developing The Multi-Agent System

Building out a multi-agent system can be broken down into 3 high-level steps,
provided below:

1. Build core services (i.e., message queue and control plane)
2. Build the agents
3. Build any additional system services (e.g., human consumer service)

### Step 1: Build core services

In this step, you build the message queue, which is the main communication broker
used by all entities in the system, as well as the control plane. It bears
mentioning that within the control plane lies the orchestrator that has the
responsibility of determining the execution flow of the task.

#### Code snippet for defining your system's message queue

```python
from llama_agents import SimpleMessageQueue

message_queue = SimpleMessageQueue(host=..., port=...)
app = message_queue._app  # fastapi app extracted for Docker deployment
```

#### Code snippet for defining your system's control plane

```python
from llama_agents import (
    AgentOrchestrator,
    ControlPlaneServer,
    SimpleMessageQueue,
)
from llama_index.llms.openai import OpenAI

# setup message queue
message_queue = SimpleMessageQueue(host=..., port=...)
queue_client = message_queue.client

# setup control plane
control_plane = ControlPlaneServer(
    message_queue=queue_client,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
    host=...,
    port=...,
)

app = control_plane.app  # fastapi app extracted for Docker deployment
```

### Step 2: Build the agents

Fill in

### Step 3: Build additional services

Fill in

## Launching Multi-Agent System

In this example, we demonstrate how one can launch their multi-agent system
using three different options:

1. Launching Services Without Docker
2. Launching Services With Docker
3. Launching Services With Kubernetes

These options can be thought of as a progression scale that may be used depending
on the current stage of the development process. Specifically, during early
stages of development, rapid iteration cycles on the components are likely of
higher priority, and so launching without docker might seem appropriate. The next
stage may then be to progress the system towards production, where containerization
becomes essential. Finally, when the matters of scalability and orchestrating these
various services become of higher priority, one may want to test launching the system
on a localized Kubernetes cluster.

### Launching Without Docker

An easy way to launch a multi-agent system is to use `ServerLauncher` object. This
object takes in all of the core, agent and additional services and makes launching
them into a single method execution call.

```python
from llama_agents import ServerLauncher

# Multi-Agent System
# core services
message_queue = ...
control_plane = ...
# agent services
secret_agent_server = ...
funny_agent_server = ...
# additional services
human_consumer_server = ...

# Server Launcher
launcher = ServerLauncher(
    [secret_agent_server, funny_agent_server],
    control_plane,
    message_queue,
    additional_consumers=[human_consumer_server.as_consumer()],
)

# launch the darn thing
launcher.launch_servers()
```

Before launching we first need to set the required environment variables. To do
that fill in the provided `template.env.local` file provided in the `multi-agent-app/` folder. After filling in the file rename it to `.env.local` (i.e., remove "template" from the name).

```sh
# set environment variables
set -a && source multi-agent-app/.env.local

# activate the project virtual env
cd multi-agent-app/
poetry shell
poetry install
```

To launch the example multi-agent system app:

```sh
python multi-agent-app/multi_agent_app/local_launcher.py
```

### Launching With Docker

_Prerequisites_: Must have docker installed. (See [here](https://docs.docker.com/get-docker/) for how to install Docker Desktop which comes with `docker-compose`.)

To Launch with Docker, this example makes use of `docker-compose` that will take
care of launching the individual services (and building a default bridge network
so that the services/containers can communicate with one another by name.).

With our multi-agent-app setup, we only need to build one common Docker image
from which we can run the individual services. The `Dockerfile` for that common
image is found in `multi-agent-app/Dockerfile`. Before building the docker image
and launching the services

As with local launcher, we first need to set the required environment variables.
Fill in the values in the `template.env.docker` file and after doing so rename the
file to `.env.docker`. Note there are some variables there that we recommend not
modifying as they are used to the service definitions establisehed in the
`docker_compose.yml`.

To launch the services we now use the `docker-compose` command line tool.

```sh
docker-compose up --build
```

Once all the services are up and running, which one can check by running
`docker ps` and checking that all the services are of 'healthy' status, we must
register our services to the message queue as well as control plane.

```sh
set -a && source multi-agent-app/.env.docker
export MESSAGE_QUEUE=0.0.0.0
make register
```

### Launching With Kubernetes

...
