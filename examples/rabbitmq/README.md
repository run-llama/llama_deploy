# Examples using RabbitMQ Work Queues as the MessageQueue

The examples contained in this subdirectory make use of the RabbitMQ integration
within `llama-agents`.

To run these examples, you'll need to have the installed the `rabbitmq` extra:

```sh
# using pip install
pip install llama-agents[rabbitmq]

# using poetry
poetry add llama-agents -E "rabbitmq"
```

## Usage Pattern

```python
from llama_agents.message_queue.rabbitmq import RabbitMQMessageQueue

message_queue = RabbitMQMessageQueue(
    url=...
)  # if no url is supplied the default localhost is used
```

## Examples

### Simple Scripts

A couple of scripts using `LocalLauncher` and a `LocalServer` with
`RabbitMQMessageQueue` (rather than `SimpleMessageQueue`) are included in this
subdirectory.

Before running any of these scrtips we first need to have RabbitMQ server running.
For a quick setup, we recommend using the official RabbitMQ community docker image:

```sh
# latest RabbitMQ 3.13
docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management
```

With our RabbitMQ server running, we can now run our example scripts.

```sh
# using LocalLauncher
python ./simple-scripts/local_launcher_example.py
```

The script above will build a simple multi-agent app, connect it to the RabbitMQ
message queue, and subsequently send the specified task.

### Example App: `multi-agent-app` revisited

In this section, we re-consider the `multi-agent-app` first found in the parent
examples folder: `examples/docker-kubernetes`. We will go through this example
as we did before, explaining how you could launch the `multi-agent-app` with three
different launchers:

1. Without Docker using `LocalLauncher`
2. With Docker (i.e., using `docker-compose`)
3. With Kubernetes (i.e., using `kubectl`)

The main difference of course being that this time we will be using `RabbitMQMessageQueue`
rather than `SimpleMessageQueue` as our message broker between the services/workers.

#### Launching Without Docker

As with running our example simple scripts above, we need to standup our RabbitMQ
manually:

```sh
# latest RabbitMQ 3.13
docker run -it --rm --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3.13-management
```

Next, in order to launch this multi-agent system, we first need to set the
required environment variables. To do that fill in the provided
`template.env.local` file found in the `multi-agent-app-rabbitmq/` folder. After filling
in the file rename it to `.env.local` (i.e., remove "template" from the name)
and the run the commands that follow.

```sh
# set environment variables
set -a && source multi-agent-app-rabbitmq/.env.local

# activate the project virtual env
cd multi-agent-app-rabbitmq/ && poetry shell && poetry install && cd ../
```

Finally to launch the example multi-agent app:

```sh
python multi-agent-app-rabbitmq/multi_agent_app/local_launcher.py
```

Once launched, we can send tasks to our multi-agent system using the
`LlamaAgentsClient` (note: the code below introduce static delay to handle
asynchronous call for quick test purpose only):

```python
from llama_agents import LlamaAgentsClient
import time

client = LlamaAgentsClient("http://0.0.0.0:8001")
task_id = client.create_task("What is the secret fact?")
time.sleep(10)
task_result = client.get_task_result(task_id)
print(task_result.result)
```

#### Launching With Docker

_Prerequisites_: Must have docker installed. (See
[here](https://docs.docker.com/get-docker/) for how to install Docker Desktop
which comes with `docker-compose`.)

**NOTE:** In this example, we don't need to run the RabbitMQ server manually. So you
can go ahead and shutdown the RabbitMQ docker container that we had running in
previous launch if you haven't yet done so. The RabbitMQ server is bundled within
the multi-agent deployment defined in the `docker-compose.yaml` file.

To Launch with Docker, this example makes use of `docker-compose` that will take
care of launching the individual services (and building a default bridge network
so that the services/containers can communicate with one another by name.).

Before building the docker image and launching the services (as with the case
for launching without Docker), we first need to set the required environment
variables. Fill in the values in the `template.env.docker` file and after doing so rename
the file to `.env.docker`. Note there are some variables there that we recommend
not modifying as they are used to the service definitions establisehed in the
`docker_compose.yml`.

This example is provided without a `poetry.lock` file as recommended in the
[poetry documentation for library developers](https://python-poetry.org/docs/basic-usage/#as-a-library-developer).
Before running docker-compose the first time, we must create the `poetry.lock`
file.

`cd examples/docker-kubernetes/multi-agent-app-rabbitmq && poetry install`

To launch the services we now use the `docker-compose` command line tool.

```sh
docker-compose up --build
```

This command will start the servers in sequence: first the RabbitMQ service,
then the control plane, followed by the agent services and the human consumer
service. This sequencing is required since the later services depend must register
to the message queue and control plane (and they need to be up and running before
being able to do so).

Once all the services are up and running, we can send tasks to our multi-agent
system:

```python
from llama_agents import LlamaAgentsClient
import time

client = LlamaAgentsClient("http://0.0.0.0:8001")
task_id = client.create_task("What is the secret fact?")
time.sleep(10)
task_result = client.get_task_result(task_id)
print(task_result.result)
```

#### Launching With Kubernetes

_Prerequisites_: Must have `kubectl` and local Kubernetes cluster running. The
recommended way is to install Docker Desktop which comes with a standalone
Kubernetes server & client (see
[here](https://docs.docker.com/desktop/kubernetes/) for more information.)

To launch with Kubernetes, we'll make use of `kubectl` command line tool and
"apply" our k8s manifests. For this example to run, it assumes the docker image
`multi-agent-app-rabbitmq` has already been built, which would be the case if your
continuining along from the previous launch with Docker example. If not, then
simply execute the below command to build the necessary docker image:

```sh
docker-compose build
```

In this setup, we will deploy a RabbitMQ Kubernetes cluster before launching the
rest of the multi-agent app. To do so, we'll make use of the RabbitMQ Cluster
Kubernetes Operator (for more information on RabbitMQ Kubernetes Operators, see
[here](https://www.rabbitmq.com/kubernetes/operator/operator-overview)).

The first step is to install the latest version of the RabbitMQ Cluster K8s
Operator

```sh
kubectl apply -f "https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml"
```

With this Operator, it's straightforward to standup a RabbitMQ Cluster instance.
The one that we use for this launch, is defined in `kubernetes/rabbitmq/rabbitmq.yaml`.

```sh
kubectl apply -f kubernetes/rabbitmq
```

To check that its running:

```sh
kubectl -n llama-agents-demo get all
```

Once running, we can proceed with deploying the rest of the multi-agent app! As before with local and Docker, we need to fill in our secrets. But instead of
an .env that we need to modify, it will be a .yaml file. Specifically, fill in
the `OPENAI_API_KEY` value within the `kubernetes/setup/secrets.yaml.template`
file. After doing so, rename the file to `secrets.yaml`.

To launch the services we use the below commands:

```sh
kubectl apply -f kubernetes/setup
kubectl apply -f kubernetes/ingress_controller
kubectl apply -f kubernetes/ingress_services
```

Once all the pods are of "Running" status, we can send tasks to our multi-agent
system:

```python
from llama_agents import LlamaAgentsClient
import time

client = LlamaAgentsClient("http://control-plane.127.0.0.1.nip.io")
task_id = client.create_task("What is the secret fact?")
time.sleep(10)
task_result = client.get_task_result(task_id)
print(task_result.result)
```

To view the RabbitMQ dashboard, we need to port forward the UI so we can access
it externally:

```sh
kubectl port-forward -n llama-agents-demo rabbitmq-server-2 8080:15672
```

Next, open up a browser and visit http://127.0.0.1:8080/#/. Enter "guest" for
both `user` and `password`.

![image](https://github.com/run-llama/llama-agents/assets/92402603/59a5278e-a80a-42d5-b49d-5c9708bc2d8f)
