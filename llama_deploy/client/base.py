from typing import Any

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict


class _BaseClient(BaseSettings):
    """Base type for clients, to be used in Pydantic models to avoid circular imports.

    Settings can be passed to the Client constructor when creating an instance, or defined with environment variables
    having names prefixed with the string `LLAMA_DEPLOY_`, e.g. `LLAMA_DEPLOY_DISABLE_SSL`.
    """

    model_config = SettingsConfigDict(env_prefix="LLAMA_DEPLOY_")

    api_server_url: str = "http://localhost:4501"
    control_plane_url: str = "http://localhost:8000"
    disable_ssl: bool = False
    timeout: float = 120.0
    poll_interval: float = 0.5

    async def request(
        self, method: str, url: str | httpx.URL, **kwargs: Any
    ) -> httpx.Response:
        """Performs an async HTTP request using httpx."""
        verify = kwargs.pop("verify", True)
        timeout = kwargs.pop("timeout", self.timeout)
        async with httpx.AsyncClient(verify=verify) as client:
            response = await client.request(method, url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
