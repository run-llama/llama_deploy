# LlamaIndex Server

The `src` folder contains a `workflow.py` file defining a code generation workflow:

To be able to run the workflow above within LlamaDeploy, a deployment must be defined in YAML format. This is the code
you'll find in the file `code_artifact.yml` from the current folder, with comments to the relevant bits:


## Running the Deployment

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
$ llamactl deploy code_artifact.yml
Deployment successful: CodeArtifact
```

### UI Interface

LlamaDeploy will serve the UI through the apiserver, at the address `http://localhost:4501/deployments/<deployment name>/ui`. In
this case, point the browser to [http://localhost:4501/deployments/CodeArtifact/ui](http://localhost:4501/deployments/CodeArtifact/ui) to interact
with your deployment through a user-friendly interface.

## Running with Docker

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
