# Using Redis as State Store

> [!NOTE]
> This example is mostly based on the [Quick Start](../quick_start/README.md), see there for more details.

We'll be deploying a simple workflow on a local instance of Llama Deploy using Redis as a scalable storage for the
global state. See [the Control Plane documentation](https://docs.llamaindex.ai/en/stable/module_guides/llama_deploy/20_core_components/#control-plane)
for an overview of what the global state consists of and when the default storage might not be enough.

Before starting Llama Deploy, use Docker compose to start the Redis container and run it in the background:

```
$ docker compose up -d
```

Make sure to install the package to support the Redis KV store in the virtual environment where we'll run Llama Deploy:

```
$ pip install -r requirements.txt
```

This is the code defining our deployment, with comments to the relevant bits:

```yaml
name: QuickStart

control-plane:
  port: 8000
  # Here we tell the Control Plane to use Redis
  state_store_uri: redis://localhost:6379

default-service: echo_workflow

services:
  echo_workflow:
    name: Echo Workflow
    source:
      type: local
      name: ./src
    path: workflow:echo_workflow
```

Note how we provide a connection URI for Redis in the `state_store_uri` field of the control plane configuration.

At this point we have all we need to run this deployment. Ideally, we would have the API server already running
somewhere in the cloud, but to get started let's start an instance locally. Run the following python script
from a shell:

```
$ python -m llama_deploy.apiserver
INFO:     Started server process [10842]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4501 (Press CTRL+C to quit)
```

From another shell, use the CLI, `llamactl`, to create the deployment:

```
$ llamactl deploy quick_start.yml
Deployment successful: QuickStart
```

Our workflow is now part of the `QuickStart` deployment and ready to serve requests! We can use `llamactl` to interact
with this deployment:

```
$ llamactl run --deployment QuickStart --arg message 'Hello from my shell!'
Message received: Hello from my shell!
```
