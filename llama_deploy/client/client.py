from .base import _BaseClient
from .models import ApiServer


class Client(_BaseClient):
    """Fixme.

    Fixme.
    """

    @property
    def sync(self) -> "Client":
        return _SyncClient(**self.settings.model_dump())

    @property
    def apiserver(self) -> ApiServer:
        return ApiServer.instance(client=self, id="apiserver")


class _SyncClient(Client):
    @property
    def apiserver(self) -> ApiServer:
        return ApiServer.instance(make_sync=True, client=self, id="apiserver")
