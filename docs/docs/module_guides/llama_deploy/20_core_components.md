# Core Components

LlamaDeploy consists of several core components acting as services in order to provide the environment where
multi-agent applications can run and communicate with each other. This sections details each and every component and
will help you navigate the rest of the documentation.

## Deployment

In LlamaDeploy each workflow is wrapped in a [_Service_](#service) object, endlessly processing incoming requests in
form of [_Task_](#task) objects. Each service pulls and publishes messages to and from a [_Message Queue_](#message-queue).
An internal component called [_Control Plane_](#control-plane) handles ongoing tasks, manages the internal state, keeps
track of which services are available, and decides which service to forward a [_Task_](#task) to.

A well defined set of these components is called _Deployment_.

Deployments can be defined with YAML code, for example:

```yaml
name: QuickStart

control-plane:
  port: 8000

default-service: dummy_workflow

services:
  dummy_workflow:
    name: Dummy Workflow
    source:
      type: local
      name: src
    path: workflow:echo_workflow
```

For more details, see the API reference for the deployment [`Config`](../../api_reference/llama_deploy/apiserver.md#llama_deploy.apiserver.deployment_config_parser.DeploymentConfig) object.

## API Server

The API Server is a core component of LlamaDeploy responsible for serving and managing multiple deployments at the same time,
and it exposes a HTTP API that can be used for administrative purposes as well as for querying the deployed services.
You can interact with the administrative API through [`llamactl`](./40_llamactl.md) or the [Python SDK](./30_python_sdk.md).

For more details see [the Python API reference](../../api_reference/llama_deploy/apiserver.md), while the administrative
API is documented below.

!!swagger apiserver.json!!

## Task

A Task is an object representing a request for an operation sent to a Service and the response that will be sent back.
For the details you can look at the [API reference](../../api_reference/llama_deploy/types.md)
