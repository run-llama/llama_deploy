# Message Queue Integrations Example

With this example, we demonstrate how to use each of the message queues supported
within `llama-deploy`. Specifically, there is only one single example application,
for which we show how to use the various message queues.

## Setup

_Prerequisites_: Must have docker installed. (See
[here](https://docs.docker.com/get-docker/) for how to install Docker Desktop
which comes with `docker-compose`.)

Before we can deploy the app, we need to first install it. To do so, we use `poetry`:

```sh
cd _app
poetry shell
poetry install
cd ../
```

The above command builds the application and creates the `poetry.lock` file which
is required in building the Docker image.

Finally, we also need to provide an `OPENAI_API_KEY` as the workflow in the app
requires it. We provide this key in the `template.env.openai` file. After supplying
the key, rename the file to `.env.openai` (i.e., drop "template" from the file name).
Our Docker orchestration looks for this `.env.openai` file so make sure not to
miss this step.

## Deploying the app

Now, to deploy the app we need a single `docker compose` command. (All of the message
queues have their own `docker-compose.yaml` file contained in their respective
subfolders.)

Using any one of the commands (while in the parent `/message-queue-integrations` folder)
below will spin the example app using the associated message queue.

```sh
# simple message queue
docker compose -f ./simple/docker/docker-compose.yml --project-directory ./ up --build -d

# aws
docker compose -f ./aws/docker/docker-compose.yml --project-directory ./ up --build -d

# kafka
docker compose -f ./kafka/docker/docker-compose.yml --project-directory ./ up --build -d

# rabbitmq
docker compose -f ./rabbitmq/docker/docker-compose.yml --project-directory ./ up --build -d

# redis
docker compose -f ./redis/docker/docker-compose.yml --project-directory ./ up --build -d

# solace
docker compose -f ./solace/docker/docker-compose.yml --project-directory ./ up --build -d
```

NOTE: In a real-world app, you would only use one of these message queues. So, in
building your application (i.e., see `_app/`) you would not need to include the
other message queues in your source code as we've done here.

### Interacting with the system

Once the system is up and running, we can interact with it using the `LlamaDeployClient`:

```python
from llama_deploy import LlamaDeployClient
from llama_deploy.control_plane.server import ControlPlaneConfig

# Set up control plane configuration
control_plane_config = ControlPlaneConfig(host="0.0.0.0", port=8000)

# Create a client to interact with the deployed system
client = LlamaDeployClient(control_plane_config)

# Start a session and run the funny joke workflow
session = client.create_session()
result = session.run("funny_joke_workflow", input="llamas")

# Print the result
print(result)
```

## Deploying with Kubernetes

Some of the message queue folders contain a `/kubernetes` subfolder, where
Kubernetes manifests that are used to deploy the example app with K8s can be found.
Refer to the README contained in the `/kubernetes` folder for instructions on how
to use those manifests to deploy the app with Kubernetes.
