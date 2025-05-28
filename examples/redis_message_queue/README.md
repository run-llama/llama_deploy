# Using Redis as Message Queue provider

> [!NOTE]
> This example is mostly based on the [Quick Start](../quick_start/README.md), see there for more details.

We'll be deploying a simple workflow on a container running LlamaDeploy using Redis as the message queue
provider. The Redis container will be started in a different container using Docker Compose.

This is the code defining our deployment, with comments to the relevant bits:

```yaml
name: RedisMessageQueue

control-plane:
  port: 8000

message-queue:
  type: redis
  # what follows depends on what's in the docker compose file
  host: redis
  port: 6379

default-service: counter_workflow_service

services:
  counter_workflow_service:
    name: Counter Workflow
    source:
      type: local
      name: .
    path: workflow:counter_workflow
```

Note how we the deployment file contains the `message-queue` key to instruct LlamaDeploy to use
Redis as the message queue provider.

Before starting the containers, two things to note about how LlamaDeploy is configured:

- We mount our application, consisting of the `deployment.yml` file and a Python
module `workflow.py` containing the LlamaIndex code implementing the workflow, under the path
`/opt/app` inside the container
- We set the `LLAMA_DEPLOY_APISERVER_RC_PATH` environment variable so that when LlamaDeploy
starts, it will look under the `/opt/app` folder for deployments to create automatically.

We can now start the Docker containers using Compose:

```
$ docker compose up -d
```

When the containers are up and running, we can use `llamactl` from our local host to
interact with the deployment:

```
$ llamactl status
LlamaDeploy is up and running.

Active deployments:
- RedisMessageQueue
```

Our workflow is now part of the `RedisMessageQueue` deployment and ready to serve requests! Since we want to persist
a counter across workflow runs, first we manually create a session:

```
$ llamactl sessions create -d RedisMessageQueue
session_id='<YOUR_SESSION_ID>' task_ids=[] state={}
```

Then we run the workflow multiple times, always using the same session we created in the previous step:

```
$ lamactl run --deployment RedisMessageQueue --arg amount 3 -i <YOUR_SESSION_ID>
Current balance: 3.0
$ lamactl run --deployment RedisMessageQueue --arg amount 3 -i <YOUR_SESSION_ID>
Current balance: 3.5
```

_Note_: If you have multiple replicas of the workflow and control plane and only want one replica to process messages,
set `REDIS_EXCLUSIVE_MODE` to true.
