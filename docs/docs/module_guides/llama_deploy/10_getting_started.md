# Getting Started

Let's start with deploying a simple workflow on a local instance of LlamaDeploy. After installing LlamaDeploy, create
a `src` folder and a `workflow.py` file to it containing the following Python code:

```python
import asyncio
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step


class EchoWorkflow(Workflow):
    """A dummy workflow with only one step sending back the input given."""

    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        message = str(ev.get("message", ""))
        return StopEvent(result=f"Message received: {message}")


# `echo_workflow` will be imported by LlamaDeploy
echo_workflow = EchoWorkflow()


async def main():
    print(await echo_workflow.run(message="Hello!"))


# Make this script runnable from the shell so we can test the workflow execution
if __name__ == "__main__":
    asyncio.run(main())
```

Test the workflow runs locally:

```
$ python src/workflow.py
Message received: Hello!
```

Time to deploy that workflow! Create a file called `deployment.yml` containing the following YAML code:

```yaml
name: QuickStart

control-plane:
  port: 8000

default-service: echo_workflow

services:
  echo_workflow:
    name: Echo Workflow
    # We tell LlamaDeploy where to look for our workflow
    source:
      # In this case, we instruct LlamaDeploy to look in the local filesystem
      type: local
      # The path relative to this deployment config file where to look for the code. This assumes
      # there's an src folder along with the config file containing the file workflow.py we created previously
      name: ./src
    # This assumes the Python module workflow.py contains a variable called `echo_workflow`
    # containing our workflow instance
    path: workflow:echo_workflow
```

The YAML code above defines the deployment that LlamaDeploy will create and run as a service. As you can
see, this deployment has a name, some configuration for the control plane and one service to wrap our workflow. The
service will look for a Python variable named `echo_workflow` in a Python module named `workflow` and run the workflow.

At this point we have all we need to run this deployment. Ideally, we would have the API server already running
somewhere in the cloud, but to get started let's start an instance locally. Run the following python script from a shell:

```
$ python -m llama_deploy.apiserver
INFO:     Started server process [10842]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4501 (Press CTRL+C to quit)
```

From another shell, use `llamactl` to create the deployment:

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

LlamaDeploy comes with Docker images that can be used to run the API server without effort. In the previous example,
if you have Docker installed, you can replace running the API server locally with `python -m llama_deploy.apiserver`
with:

```
$ docker run -p 4501:4501 -v .:/opt/quickstart -w /opt/quickstart llamaindex/llama-deploy:main
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:4501 (Press CTRL+C to quit)
```

The API server will be available at `http://localhost:4501` on your host, so `llamactl` will work the same as if you
run `python -m llama_deploy.apiserver`.

> [!NOTE]
> The `llamaindex/llama-deploy:main` Docker image is continuously built from the latest commit in the `main`
> branch of the git repository. While this ensures you get the most recent version of the project, the
> image might contain unreleased features that are not fully stable, use with caution!
