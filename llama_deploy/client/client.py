from .base import _BaseClient
from .models import ApiServer, Core


class Client(_BaseClient):
    """The Llama Deploy Python client.

    The client is gives access to both the asyncio and non-asyncio APIs. To access the sync
    API just use methods of `client.sync`.

    Example usage:
    ```py
    from llama_deploy.client import Client

    # Use the same client instance
    c = Client()

    async def an_async_function():
        status = await client.apiserver.status()

    def normal_function():
        status = client.sync.apiserver.status()
    ```
    """

    @property
    def sync(self) -> "_SyncClient":
        """Returns the sync version of the client API."""
        return _SyncClient(**self.model_dump())

    @property
    def apiserver(self) -> ApiServer:
        """Returns the ApiServer model."""
        return ApiServer.instance(client=self, id="apiserver")

    @property
    def core(self) -> Core:
        """Returns the Core model."""
        return Core.instance(client=self, id="core")


class _SyncClient(Client):
    @property
    def apiserver(self) -> ApiServer:
        return ApiServer.instance(make_sync=True, client=self, id="apiserver")

    @property
    def core(self) -> Core:
        return Core.instance(make_sync=True, client=self, id="core")
