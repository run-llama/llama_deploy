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
    ) -> httpx.Response:
        """Performs an async HTTP request using httpx."""
        verify = kwargs.pop("verify", True)
        async with httpx.AsyncClient(verify=verify) as client:
            response = await client.request(method, url, *args, **kwargs)
            response.raise_for_status()
            return response

    @property
    def sync(self) -> "Client":
        return _SyncClient(**self.settings.model_dump())

    def __getattr__(self, name):  # type: ignore
        try:
            return self._model_mappings[name](client=self, id=name)
        except KeyError:
            raise AttributeError


class _SyncClient(Client):
    _model_mappings: dict[str, type[Model]] = {"apiserver": make_sync(ApiServer)}
