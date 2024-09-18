# Deploying With Kubernetes

_Prerequisites_: Must have `kubectl` and local Kubernetes cluster running. The
recommended way is to install Docker Desktop which comes with a standalone
Kubernetes server & client (see
[here](https://docs.docker.com/desktop/kubernetes/) for more information.)

As before with local and Docker, we need to fill in our secrets. But instead of
an .env.openai that we need to modify, it will be a .yaml file. Specifically, fill in
the `OPENAI_API_KEY` value within the `kubernetes/setup/secrets.yaml.template`
file. After doing so, rename the file to `secrets.yaml`.

```sh
cd ./rabbitmq
kubectl apply -f kubernetes/setup
```

To deploy with Kubernetes, we'll make use of `kubectl` command line tool and
"apply" our k8s manifests. For this example to run, it assumes the docker image
`multi_workflows_app` has already been built, which would be the case if you
previously deployed with Docker using the contents in the `docker/` subfolder.
If not, then simply execute the below command to build the necessary docker image:

```sh
# execute while in /message-queue-integrations folder
docker-compose -f ./rabbitmq/docker/docker-compose.yml --project-directory ./ build
```

In this setup, we will deploy a RabbitMQ Kubernetes cluster before launching the
rest of the multi-agent app. To do so, we'll make use of the RabbitMQ Cluster
Kubernetes Operator (for more information on RabbitMQ Kubernetes Operators, see
[here](https://www.rabbitmq.com/kubernetes/operator/operator-overview)).

The first step is to install the latest version of the RabbitMQ Cluster K8s
Operator

```sh
kubectl apply -f "https://github.com/rabbitmq/cluster-operator/releases/latest/download/cluster-operator.yml"
```

With this Operator, it's straightforward to standup a RabbitMQ Cluster instance.
The one that we use for this launch, is defined in `kubernetes/rabbitmq/rabbitmq.yaml`.

```sh
kubectl apply -f kubernetes/rabbitmq
```

To check that its running:

```sh
kubectl -n llama-deploy-demo get all
```

Once running, we can proceed with deploying the rest of the multi-agent app!

To launch the services we use the below commands:

```sh
kubectl apply -f kubernetes/ingress_controller
kubectl apply -f kubernetes/ingress_services
```

To view the status of the services and pods, use the following command:

```sh
kubectl -n llama-deploy-demo get pods
```

A successful launch should yield something like this:

```sh
NAME                                   READY   STATUS    RESTARTS   AGE
control-plane-766647bfc7-65p4r         1/1     Running   0          114s
funny-joke-workflow-78c75998b6-sl4gz   1/1     Running   0          114s
rabbitmq-server-0                      1/1     Running   0          4m29s
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

- `control-plane`: <http://control-plane.127.0.0.1.nip.io>
- `funny-joke-workflow`: <http://funny-joke-workflow.127.0.0.1.nip.io>

## Viewing RabbitMQ Console

To view the RabbitMQ dashboard, we need to port forward the UI so we can access
it externally:

```sh
kubectl port-forward -n llama-deploy-demo rabbitmq-server-0 8080:15672
```

Next, open up a browser and visit http://127.0.0.1:8080/#/. Enter "guest" for
both `user` and `password`.

<img width="960" alt="image" src="https://github.com/user-attachments/assets/8e6085d1-0545-4493-acd4-c8485bee953e">
