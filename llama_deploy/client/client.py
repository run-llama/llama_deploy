from typing import Any

from .models import ApiServer
from .client_settings import ClientSettings


class Client:
    """Fixme.

    Fixme.
    """

    def __init__(self, **kwargs: Any) -> None:
        self.settings = ClientSettings(**kwargs)

    @property
    def apiserver(self) -> ApiServer:
        """Returns a model to interact with the API Server"""
        return ApiServer(client=self)
