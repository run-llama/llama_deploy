import asyncio
from typing import TYPE_CHECKING

from asgiref.sync import async_to_sync

if TYPE_CHECKING:
    from llama_deploy.client import Client


class Model:
    def __init__(self, *, client: "Client"):
        self._client = client

    @property
    def client(self) -> "Client":
        return self._client


def make_sync(_class: type[Model]) -> type[Model]:
    class Wrapper(_class):  # type: ignore
        pass

    for name, method in _class.__dict__.items():
        if asyncio.iscoroutinefunction(method) and not name.startswith("_"):
            setattr(Wrapper, name, async_to_sync(method))
    return Wrapper
