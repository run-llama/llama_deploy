# Example: Launching a Multi-Agent System with Docker and Kubernetes

![Slide One](https://d3ddy8balm3goa.cloudfront.net/llamaindex/launchers.svg)

In this example, we demonstrate how one can build a multi-agent app with a
structure and development flow more conducive to production. Specifically,
we employ a project structure that organizes the multi-agent app to its separate
components, namely:

- `core_services`: message queue and control plane
- `agent_services`: our agents and their respective services
- `additional_services`: additional services such as human consumer service (which
  for this example writes the final task result json objects to `task_results/task_results.jsonl`)

In what follows next, we present three ways to launch the multi-agent system of
this example.

## Launching Multi-Agent System: Without Docker, With Docker, Kubernetes

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

In order to launch the multi-agent system of this example, we
first need to set the required environment variables. To do that fill in the
provided `template.env.local` file provided in the `multi-agent-app/` folder.
After filling in the file rename it to `.env.local` (i.e., remove "template" from
the name).

```sh
# set environment variables
set -a && source multi-agent-app/.env.local

# activate the project virtual env
cd multi-agent-app/ && poetry shell && poetry install && cd ../
```

Now to launch the example multi-agent system app:

```sh
python multi-agent-app/multi_agent_app/local_launcher.py
```

Once launched, we can send tasks to our multi-agent system:

```python
from llama_agents import LlamaAgentsClient

client = LlamaAgentsClient("http://0.0.0.0:8001")
task_id = client.create_task("What is the secret fact?")
task_result = client.get_task_result(task_id)
print(task_result.result)
```

### Launching With Docker

_Prerequisites_: Must have docker installed. (See [here](https://docs.docker.com/get-docker/)
for how to install Docker Desktop which comes with `docker-compose`.)

To Launch with Docker, this example makes use of `docker-compose` that will take
care of launching the individual services (and building a default bridge network
so that the services/containers can communicate with one another by name.).

With our multi-agent-app setup, we only need to build one common Docker image
from which we can run the individual services. The `Dockerfile` for that common
image is found in `multi-agent-app/Dockerfile`. Before building the docker image
and launching the services (as with the case for launching without Docker), we
first need to set the required environment variables.

Fill in the values in the `template.env.docker` file and after doing so rename the
file to `.env.docker`. Note there are some variables there that we recommend not
modifying as they are used to the service definitions establisehed in the
`docker_compose.yml`.

To launch the services we now use the `docker-compose` command line tool.

```sh
docker-compose up --build
```

Once all the services are of healthy status, and after the `registration_task`
exits with code 0 (which should appear in the lgos) we can send tasks to our multi-agent
system:

```python
from llama_agents import LlamaAgentsClient

client = LlamaAgentsClient("http://0.0.0.0:8001")
task_id = client.create_task("What is the secret fact?")
task_result = client.get_task_result(task_id)
print(task_result.result)
```

### Launching With Kubernetes

_Prerequisites_: Must have `kubectl` and local Kubernetes cluster running. The
recommended way is to install Docker Desktop which comes with a standalone
Kubernetes server & client (see [here](https://docs.docker.com/desktop/kubernetes/)
for more information.)

To launch with Kubernetes, we'll make use of `kubectl` command line tool and
"apply" our k8s manifests. For this example to run, it assumes the docker image
`multi-agent-app` has already been built, which would be the case if your
continuining along from the previous launch with Docker example. If not, then
simply execute the below command to build the necessary docker image:

```sh
docker-compose build
```

The Kubernetes manifest files are organized as follows:

- `ingress_controller`: We use an nginx ingress controller for our reverse proxy
  and load balancer to our ingress services
- `ingress_services`: Contains our ingress services (i.e., all of the multi-agent
  system components)
- `setup`: Sets up the Kubernetes cluster with a namespace and required secrets.
- `jobs`: Kubernetes Job for handling registration to the message queue as well
  as control plane.

As before with local and Docker, we need to fill in our secrets. But instead of
an .env that we need to modify, it will be a .yaml file. Specifically, fill in
the `OPENAI_API_KEY` value within the `kubernetes/setup/secrets.yaml.template`
file. After doing so, rename the file to `secrets.yaml`.

To launch the services we use the below commands:

```sh
kubectl apply -f kubernetes/setup
kubectl apply -f kubernetes/ingress_controller
kubectl apply -f kubernetes/ingress_services
kubectl apply -f kubernetes/jobs
```

To view the status of the services and pods

```sh
kubectl -n llama-agents-demo get pods
```

A successful launch should yield something like this

```sh
NAME                              READY   STATUS      RESTARTS   AGE
control-plane-f4bc9597-b77qc      1/1     Running     0          89s
funny-agent-68db58589f-rfmk2      1/1     Running     0          89s
human-consumer-5887c96d6c-542wl   1/1     Running     0          89s
message-queue-856b4dbc56-4f9fz    1/1     Running     0          89s
registration-ppwhz                0/1     Completed   0          81s
secret-agent-578f9bc4df-hklbv     1/1     Running     0          89s
```

Note that the `registration-xxxxx` job must have Status "Completed" that signals
that all of the services were registered to the message queue and control plane.

Once all the pods are of "Running" status, we can send tasks to our multi-agent
system:

```python
from llama_agents import LlamaAgentsClient

client = LlamaAgentsClient("http://control-plane.127.0.0.1.nip.io")
task_id = client.create_task("What is the secret fact?")
task_result = client.get_task_result(task_id)
print(task_result.result)
```

NOTE: With this deployment, the services can be hit (i.e. with Postman) using
the following hosts:

- `message-queue`: http://message-queue.127.0.0.1.nip.io
- `control-plane`: http://control-plane.127.0.0.1.nip.io
- `secret-agent`: http://secret-agent.127.0.0.1.nip.io
- `funny-agent`: http://funny-agent.127.0.0.1.nip.io
- `human-consumer`: http://human-consumer.127.0.0.1.nip.io

#### Scaling the multi-agent system

We can scale up our multi-agent system by adding more "pods" for any of the
system components. For example to add another secret-agent to our system, we simply
modify the `kubernetes/ingress_services/secret_agent.yaml` file by changing the value
for `replicas` to 2:

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: secret-agent
  namespace: llama-agents-demo
spec:
  replicas: 2  # set to desired number of secret-agents
  ...
```

After making the edits, we apply the changes:

```sh
kubectl apply -f kubernetes/ingress_services
```
