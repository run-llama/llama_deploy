from typing import Any

import httpx

from .client_settings import ClientSettings


class _BaseClient:
    """Base type for clients, to be used in Pydantic models to avoid circular imports."""

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
