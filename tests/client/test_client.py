from unittest import mock

import pytest

from llama_deploy.client import Client
from llama_deploy.client.client import _SyncClient
from llama_deploy.client.models import ApiServer, Core


def test_client_init_default() -> None:
    c = Client()
    assert c.api_server_url == "http://localhost:4501"
    assert c.disable_ssl is False
    assert c.timeout == 120.0
    assert c.poll_interval == 0.5


def test_client_init_settings() -> None:
    c = Client(api_server_url="test")
    assert c.api_server_url == "test"


def test_client_sync() -> None:
    c = Client()
    sc = c.sync
    assert type(sc) is _SyncClient
    assert sc.api_server_url == "http://localhost:4501"
    assert sc.disable_ssl is False
    assert sc.timeout == 120.0
    assert sc.poll_interval == 0.5


@pytest.mark.asyncio
async def test_client_sync_within_loop() -> None:
    c = Client()
    with pytest.raises(
        RuntimeError,
        match="You cannot use the sync client within an async event loop - just await the async methods directly.",
    ):
        c.sync


def test_client_attributes() -> None:
    c = Client()
    assert type(c.apiserver) is ApiServer
    assert type(c.core) is Core
    assert issubclass(type(c.sync.apiserver), ApiServer)
    assert issubclass(type(c.sync.core), Core)


@pytest.mark.asyncio
async def test_client_request() -> None:
    with mock.patch("llama_deploy.client.base.httpx") as _httpx:
        mocked_response = mock.MagicMock()
        _httpx.AsyncClient.return_value.__aenter__.return_value.request.return_value = (
            mocked_response
        )

        c = Client()
        await c.request("GET", "http://example.com", verify=False)
        _httpx.AsyncClient.assert_called_with(verify=False)
        mocked_response.raise_for_status.assert_called_once()
