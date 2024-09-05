# Deploying With Kubernetes

_Prerequisites_: Must have `kubectl` and local Kubernetes cluster running. The
recommended way is to install Docker Desktop which comes with a standalone
Kubernetes server & client (see
[here](https://docs.docker.com/desktop/kubernetes/) for more information.)

To deploy with Kubernetes, we'll make use of `kubectl` command line tool and
"apply" our k8s manifests. For this example to run, it assumes the docker image
`multi_workflows_app` has already been built, which would be the case if you
previously deployed with Docker using the contents in the `docker/` subfolder.
If not, then simply execute the below command to build the necessary docker image:

```sh
# execute while in /message-queue-integrations folder
docker-compose -f ./simple/docker/docker-compose.yml --project-directory ./ build
```

The Kubernetes manifest files are organized as follows:

- `ingress_controller`: We use an nginx ingress controller for our reverse proxy
  and load balancer to our ingress services
- `ingress_services`: Contains our ingress services (i.e., all of the
  system components)
- `setup`: Sets up the Kubernetes cluster with a namespace and required secrets.

As before with local and Docker, we need to fill in our secrets. But instead of
an .env.openai that we need to modify, it will be a .yaml file. Specifically, fill in
the `OPENAI_API_KEY` value within the `kubernetes/setup/secrets.yaml.template`
file. After doing so, rename the file to `secrets.yaml`.

To launch the services we use the below commands:

```sh
cd ./simple
kubectl apply -f kubernetes/setup
kubectl apply -f kubernetes/ingress_controller
kubectl apply -f kubernetes/ingress_services
```

NOTE: the last command will deploy `control-plane`, `message-queue` and
`funny-joke-workflow` simultaneously, which should work most of the time. An
improvement to this deployment procedure would be to ensure the proper sequencing
of deployment of these services: `message-queue`, followed by `control-plane`, and
finally followed by `funny-joke-workflow`.

To view the status of the services and pods

```sh
kubectl -n llama-deploy-demo get pods
```

A successful launch should yield something like this

```sh
NAME                                   READY   STATUS    RESTARTS   AGE
control-plane-5ddbf96dd5-7x4x2         1/1     Running   0          5m7s
funny-joke-workflow-69ff9595f6-bn4dt   1/1     Running   0          5m7s
message-queue-5f6d8578b8-jx267         1/1     Running   0          5m7s
```

Once all the pods are of "Running" status, we can send tasks to our system:

```python
from llama_deploy import LlamaDeployClient
from llama_deploy.control_plane.server import ControlPlaneConfig

control_plane_config = ControlPlaneConfig(
    host="control-plane.127.0.0.1.nip.io", port=None
)
client = LlamaDeployClient(control_plane_config)
session = client.create_session()
result = session.run(
    "funny_joke_workflow", input="A baby llama is called a cria."
)
print(result)
```

NOTE: With this deployment, the services can be hit (i.e. with Postman) using
the following hosts:

- `message-queue`: <http://message-queue.127.0.0.1.nip.io>
- `control-plane`: <http://control-plane.127.0.0.1.nip.io>
- `funny-joke-workflow`: <http://funny-joke-workflow.127.0.0.1.nip.io>

## Scaling the multi-agent system

We can scale up our multi-agent system by adding more "pods" for any of the
system components. For example to add another secret-agent to our system, we
simply modify the `kubernetes/ingress_services/workflow_funny_joke.yaml` file by
changing the value for `replicas` to 2:

```yaml
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: funny-joke-workflow
  namespace: llama-demo-demo
spec:
  replicas: 2  # set to desired number of secret-agents
  ...
```

After making the edits, we apply the changes:

```sh
kubectl apply -f kubernetes/ingress_services
```
