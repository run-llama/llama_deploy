from unittest import mock

import pytest

from llama_deploy.client import Client
from llama_deploy.client.client import _SyncClient
from llama_deploy.client.models.apiserver import ApiServer


def test_client_init_default() -> None:
    c = Client()
    settings = c.settings
    assert settings.api_server_url == "http://localhost:4501"
    assert settings.disable_ssl is False
    assert settings.timeout == 120.0
    assert settings.poll_interval == 0.5


def test_client_init_settings() -> None:
    c = Client(api_server_url="test")
    assert c.settings.api_server_url == "test"


def test_client_sync() -> None:
    c = Client()
    sc = c.sync
    assert type(sc) is _SyncClient
    settings = sc.settings
    assert settings.api_server_url == "http://localhost:4501"
    assert settings.disable_ssl is False
    assert settings.timeout == 120.0
    assert settings.poll_interval == 0.5


def test_client_attributes() -> None:
    c = Client()
    assert type(c.apiserver) is ApiServer
    assert issubclass(type(c.sync.apiserver), ApiServer)


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
