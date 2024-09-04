# Example application using RabbitMQ Work Queues as the MessageQueue

The example app contained in this subdirectory make use of the RabbitMQ integration
within `llama-deploy`.

To run these example, you'll need to have the installed the `rabbitmq` extra:

```sh
# using pip install
pip install llama-deploy[rabbitmq]

# using poetry
poetry add llama-deploy -E "rabbitmq"
```

## Usage Pattern

```python
from llama_deploy.message_queue.rabbitmq import RabbitMQMessageQueue

message_queue = RabbitMQMessageQueue(
    url=...
)  # if no url is supplied the default localhost is used
```

## Deploying the example app

In this section, we deploy a system comprised of multiple workflows that collaborate
to accomplish a task. The source code for the app is structured as follows:

```sh
multi-workflows-rabbitmq
├── Dockerfile
├── README.md
├── multi_workflows_rabbitmq
│   ├── __init__.py
│   ├── deployment
│   └── workflows
└── pyproject.toml
```

All of the workflows are contained in the `multi_workflows_rabbitmq/workflows`
subfolder, and all of the deployment related code is contained in `multi_workflows_rabbitmq/deployment`.

Next, we will go through how to deploy your multi-workflow system using either
Docker or Kubernetes as a means to orchestrate the `WorkflowService`'s.

1. With Docker (i.e., using `docker-compose`)
2. With Kubernetes (i.e., using `kubectl`)

### Deploying With Docker

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
then the control plane, followed by the workflow services. This sequencing is required since the later services depend must register to the message queue and control plane (and they need to be up and running before being able to do so).

Once all the services are up and running, we can send tasks to our system:

```python
from llama_deploy import LlamaDeployClient
from llama_deploy.control_plane.server import ControlPlaneConfig

control_plane_config = ControlPlaneConfig(host="0.0.0.0", port=8000)
client = LlamaDeployClient(control_plane_config)
session = client.create_session()
result = session.run(
    "funny_joke_workflow", input="A baby llama is called a cria."
)
print(result)
```

### Deploying With Kubernetes

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
