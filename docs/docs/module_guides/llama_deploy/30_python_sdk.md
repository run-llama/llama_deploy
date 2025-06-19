# Python SDK

LlamaDeploy provides a Python SDK for interacting with deployed systems. The SDK supports both synchronous and
asynchronous operations through a unified client interface. The asynchronous API is recommended for production use.

## Getting started

Creating a client is as simple as this:

```python
import llama_deploy

client = llama_deploy.Client()
```

## Client Configuration

The client can be configured either through constructor arguments or environment variables.
To set a configuration parameter through environment variables, their name should be the
uppercase version of the parameter name, prefixed by the string `LLAMA_DEPLOY_`:

```python
import os
import llama_deploy

# Set `disable_ssl` to False with an environment variable
os.environ["LLAMA_DEPLOY_DISABLE_SSL"] = "False"


async def check_status():
    # Pass other config settings to the Client constructor
    client = llama_deploy.Client(
        api_server_url="http://localhost:4501", timeout=10
    )
    status = await client.apiserver.status()
    print(status)
```

> [!NOTE]
> For a list of all the available configuration parameters, see the dedicated
> [API Reference section](../../api_reference/llama_deploy/python_sdk.md).

## Client Components

The client provides access to two main components:

- `apiserver`: Interact with the [API server](./20_core_components.md#api-server)

Each component exposes specific methods for managing and interacting with the deployed system.

> [!IMPORTANT]
> To use the `apiserver` functionalities, the API Server must be up and its URL
> (by default `http://localhost:4501`) reachable by the host executing the client code.


For a complete list of available methods and detailed API reference, see the
[API Reference section](../../api_reference/llama_deploy/python_sdk.md).

## Usage Examples

### Asynchronous Operations

```python
import llama_deploy


async def check_status():
    client = llama_deploy.Client()
    status = await client.apiserver.status()
    print(status)
```

### Synchronous Operations

```python
import llama_deploy

client = llama_deploy.Client()
status = client.sync.apiserver.status()
print(status)
```

> [!IMPORTANT]
> The synchronous API (`client.sync`) cannot be used within an async event loop.
> Use the async methods directly in that case.
