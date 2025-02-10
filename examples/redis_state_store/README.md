# Using Redis as State Store

> [!NOTE]
> This example is mostly based on the [Quick Start](../quick_start/README.md), see there for more details.

We'll be deploying a simple workflow on a local instance of LlamaDeploy using Redis as a scalable storage for the
global state. See [the Control Plane documentation](https://docs.llamaindex.ai/en/stable/module_guides/llama_deploy/20_core_components/#control-plane)
for an overview of what the global state consists of and when the default storage might not be enough.

Before starting LlamaDeploy, use Docker compose to start the Redis container and run it in the background:

```
$ docker compose up -d
```

Make sure to install the package to support the Redis KV store in the virtual environment where we'll run LlamaDeploy:

```
$ pip install -r requirements.txt
```

This is the code defining our deployment, with comments to the relevant bits:

```yaml
name: RedisStateStore

control-plane:
  port: 8000
  # Here we tell the Control Plane to use Redis
  state_store_uri: redis://localhost:6379

default-service: counter_workflow_service

services:
  counter_workflow_service:
    name: Counter Workflow
    source:
      type: local
      name: src
    path: workflow:counter_workflow
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
$ llamactl deploy redis_store.yml
Deployment successful: RedisStateStore
```

Our workflow is now part of the `RedisStateStore` deployment and ready to serve requests! Since we want to persist
a counter across workflow runs, first we manually create a session:

```
$ llamactl sessions create -d RedisStateStore
session_id='<YOUR_SESSION_ID>' task_ids=[] state={}
```

Then we run the workflow multiple times, always using the same session we created in the previous step:

```
$ lamactl run --deployment RedisStateStore --arg amount 3 -i <YOUR_SESSION_ID>
Current balance: 3.0
$ lamactl run --deployment RedisStateStore --arg amount 3 -i <YOUR_SESSION_ID>
Current balance: 3.5
```
