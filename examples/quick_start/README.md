# Quick Start

Let's start with deploying a simple workflow on a local instance of Llama Deploy. We recommend to use a virtual
environment where you installed `llama-deploy` before running any Python code from this guide.

The `src` folder contains a `workflow.py` file defining a trivial workflow:

```python
import asyncio
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step


class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        message = str(ev.get("message", ""))
        return StopEvent(result=f"Message received: {message}")
```

To begin, you can test that the workflow correctly runs locally:

```
$ python src/workflow.py
Message received: Hello!
```

To be able to run the workflow above within Llama Deploy, a deployment must be defined in YAML format. This is the code
you'll find in the file `deployment.yml` from the current folder, with comments to the relevant bits:

```yaml
name: QuickStart

control-plane:
  port: 8000

default-service: echo_workflow

services:
  echo_workflow:
    name: Echo Workflow
    # We tell Llama Deploy where to look for our workflow
    source:
      # In this case, we instruct Llama Deploy to look in the local filesystem
      type: local
      # The path in the local filesystem where to look. This assumes there's an src folder in the
      # current working directory containing the file workflow.py we created previously
      name: ./src
    # This assumes the file workflow.py contains a variable called `echo_workflow` containing our workflow instance
    path: workflow:echo_workflow
```

The YAML code above defines the deployment that Llama Deploy will create and run as a service. As you can
see, this deployment has a name, some configuration for the control plane and one service to wrap our workflow. The
service will look for a Python variable named `echo_workflow` in a Python module named `workflow` and run the workflow.

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
$ llamactl deploy deployment.yml
Deployment successful: QuickStart
```

Our workflow is now part of the `QuickStart` deployment and ready to serve requests! We can use `llamactl` to interact
with this deployment:

```
$ llamactl run --deployment QuickStart --arg message 'Hello from my shell!'
Message received: Hello from my shell!
```

### Run the API server with Docker

Llama Deploy comes with Docker images that can be used to run the API server without effort. In the previous example,
if you have Docker installed, you can replace running the API server locally with `python -m llama_deploy.apiserver`
with:

```
$ docker run -p 4501:4501 -v .:/opt/quickstart -w /opt/quickstart llamaindex/llama-deploy
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4501 (Press CTRL+C to quit)
```

The API server will be available at `http://localhost:4501` on your host, so `llamactl` will work the same as if you
run `python -m llama_deploy.apiserver`.
