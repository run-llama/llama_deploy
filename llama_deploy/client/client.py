import asyncio
from typing import Any

from .base import _BaseClient
from .models import ApiServer, Core, make_sync


class Client(_BaseClient):
    """The LlamaDeploy Python client.

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
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _SyncClient(**self.model_dump())

        msg = "You cannot use the sync client within an async event loop - just await the async methods directly."
        raise RuntimeError(msg)

    @property
    def apiserver(self) -> ApiServer:
        """Returns the ApiServer model."""
        return ApiServer(client=self, id="apiserver")

    @property
    def core(self) -> Core:
        """Returns the Core model."""
        return Core(client=self, id="core")


class _SyncClient(_BaseClient):
    @property
    def apiserver(self) -> Any:
        return make_sync(ApiServer)(client=self, id="apiserver")

    @property
    def core(self) -> Any:
        return make_sync(Core)(client=self, id="core")
