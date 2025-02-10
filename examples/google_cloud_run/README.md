# Host LlamaDeploy on Google Cloud Run


## Setup Google Cloud

In this example we'll be using the command line tool `gcloud`, but you can achieve the same
by interacting with the [Google Cloud console](https://console.cloud.google.com). If you
already have `gcloud` configured, you can skip this paragraph.

To install the `gcloud` CLI tool, follow the instructions for your platform in the
[official documentation](https://cloud.google.com/sdk/docs/install-sdk).

> [!TIP]
> If you're on Mac, the fastest way to install `gcloud` is using brew:
> `brew install --cask google-cloud-sdk`

Once `gcloud` is installed, complete its configuration by running
```sh
gcloud init
```

The command will ask you a few questions about your Google Cloud account and authenticate the tool.

## Create a Docker image repository for your Google account

To be able to schedule our containers in Cloud Run, the corresponding Docker images must be
hosted in the artifact registry on Google Cloud. If have one already, you can skip this
paragraph.

We need to specify the cloud region when creating the repository, in this example we're using
`europe-west1` but you can use one closer to you, just make sure you always use the same
thoroughout this example. We also need to give the repository a name, for example `llamadeploy-docker-repo`.
From the command line run:
```sh
gcloud artifacts repositories create llamadeploy-docker-repo --repository-format=docker --location=europe-west1
```

To make sure everything works correctly, run:
```sh
gcloud artifacts repositories describe llamadeploy-docker-repo --location=europe-west1
```

You should see the details about the artifact repository we just created. Take note of the field
`registryUri` because we're going to use it to address the repository in our `docker` commands. The
field should look like this:
```
registryUri: europe-west1-docker.pkg.dev/your-gcp-project-id/llamadeploy-docker-repo
```

Last but not least, run this command to let our `docker` command authenticate automatically with
our artifact repository (adjust the clour region as needed):
```sh
gcloud auth configure-docker europe-west1-docker.pkg.dev
```

## Build a custom Docker image including your LlamaIndex workflows

While LlamaDeploy supports pulling code from Github when you deploy a LlamaIndex workflow,
in this example we want to build a custom Docker image that also contains our code. This
strategy will make our deployments faster and with a stronger versioning, since we know
exactly which code will be executed: the one we added to the image at build time.

Assuming you have Docker configured in your local environment, first of all let's pull
the most recent version of the LlamaDeploy base image:
```sh
docker pull llamaindex/llama-deploy:main
```

From the folder containing this README file, `examples/google_cloud_run/`, let's
build a custom Docker image and tag it with the URI pointing to our Google Cloud artifact
repository. To build this URI use the `registryUri` field from the output of the
`gcloud artifacts repositories describe` command. The format of the tag should be
`<URI of your artifact repository>/<name of the container>:<version>`, run the following
command adjusting it for your value of `registryUri`:
```sh
docker buildx build --platform linux/amd64 -t europe-west1-docker.pkg.dev/your-project-id/llamadeploy-docker-repo/cloud-run-example:1 --build-arg SOURCE_DIR=./src .
```

> [!NOTE]
> We used `:1` as the version number, but you can use any suffix that makes sense to you, like the semantic versioning of
> your application `:0.1.0` or a more generic label `:prod`.

If everything went well, push the container to the artifact repository so that Cloud Run can
later use it:
```sh
docker push europe-west1-docker.pkg.dev/your-project-id/llamadeploy-docker-repo/cloud-run-example:1
```

## Run your custom container on Cloud Run

At this point the Docker image we want to run should be ready to be pulled by Cloud Run from our
artifact repository. To create a Cloud Run Service that will run our image behind a public URL
run this command:
```sh
gcloud run deploy --image=europe-west1-docker.pkg.dev/your-project-id/llamadeploy-docker-repo/cloud-run-example:1
```

You'll be prompted for the service name (you can leave the one proposed), the region (make sure you pick the same
as your artifact repository) and you'll be asked _"Allow unauthenticated invocations to [cloud-run-example] (y/N)?"_.
Make sure to answer yes to this one so that your deployment will be public accessible.

Once the Cloud Run service is up and running, `gcloud` will print on the terminal the details, take note of the
`Service URL` field: that's where we will point `llamactl` from now on. It should look something like this:
```
Service URL: https://cloud-run-example-123456.europe-west1.run.app
```

## Interact with your workflow

LlamaDeploy is now running on Cloud Run, and since we added our `deployment.yml` file to the
docker image itself and set the `LLAMA_DEPLOY_APISERVER_RC_PATH` environment variable, the
container automatically loaded the deployment at start up.

To confirm the container booted up correctly, run:
```sh
llamactl -s https://cloud-run-example-123456.europe-west1.run.app status
```

You should see something like this on your terminal:
```
LlamaDeploy is up and running.

Active deployments:
- CloudRunExample
```

Since everything looks good, we can run a task:
```sh
llamactl -s https://cloud-run-example-123456.europe-west1.run.app run --deployment CloudRunExample --arg message 'Hello from my laptop!'
```
You should see the output of the workflow:
```
Message received: Hello from my laptop!
```
