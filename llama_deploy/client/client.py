from typing import Any

import httpx

from .client_settings import ClientSettings
from .models import ApiServer, Model, make_sync


class Client:
    """Fixme.

    Fixme.
    """

    _model_mappings: dict[str, type[Model]] = {"apiserver": ApiServer}

    def __init__(self, **kwargs: Any) -> None:
        self.settings = ClientSettings(**kwargs)

    async def request(
        self, method: str, url: str | httpx.URL, *args: Any, **kwargs: Any
    ) -> httpx.Response | None:
        """Performs an async HTTP request using httpx."""
        verify = kwargs.pop("verify", True)
        async with httpx.AsyncClient(verify=verify) as client:
            try:
                return await client.request(method, url, *args, **kwargs)
            except httpx.ConnectError:
                return None

    @property
    def sync(self) -> "Client":
        return _SyncClient(**self.settings.model_dump())

    def __getattr__(self, name):
        try:
            return self._model_mappings[name](client=self)
        except KeyError:
            raise AttributeError


class _SyncClient(Client):
    _model_mappings: dict[str, type[Model]] = {"apiserver": make_sync(ApiServer)}
