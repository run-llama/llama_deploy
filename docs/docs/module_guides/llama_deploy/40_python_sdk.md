# Python SDK

Llama Deploy provides access to a deployed system through a synchronous and an asynchronous client. Both clients have
the same interface, but the asynchronous client is recommended for production use to enable concurrent operations.

Generally, there is a top-level client for interacting with the control plane, and a session client for interacting
with a specific session. The session client is created automatically for you by the top-level client and returned from
specific methods.

To create a client, you need to point it to a control plane.

```python
from llama_deploy import (
    LlamaDeployClient,
    AsyncLlamaDeployClient,
    ControlPlaneConfig,
)

client = LlamaDeployClient(ControlPlaneConfig())
async_client = AsyncLlamaDeployClient(ControlPlaneConfig())
```

For more details, see the dedicated [API Reference section](../../api_reference/llama_deploy/python_sdk.md).
