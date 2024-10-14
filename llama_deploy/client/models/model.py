from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llama_deploy.client import Client


class Model:
    def __init__(self, *, client: "Client"):
        self._client = client

    @property
    def client(self) -> "Client":
        return self._client
