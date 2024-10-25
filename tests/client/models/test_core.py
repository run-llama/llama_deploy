from unittest import mock

import pytest

from llama_deploy.client.models.core import Core, Service, ServiceCollection
from llama_deploy.types.core import ServiceDefinition


@pytest.mark.asyncio
async def test_service_collection_register(client: mock.AsyncMock) -> None:
    coll = ServiceCollection.instance(client=client, items={})
    service = ServiceDefinition(service_name="test_service", description="some service")
    await coll.register(service)

    client.request.assert_awaited_with(
        "POST",
        "http://localhost:8000/services/register",
        json={
            "service_name": "test_service",
            "description": "some service",
            "prompt": [],
            "host": None,
            "port": None,
        },
    )


@pytest.mark.asyncio
async def test_service_collection_deregister(client: mock.AsyncMock) -> None:
    coll = ServiceCollection.instance(client=client, items={})
    await coll.deregister("test_service")

    client.request.assert_awaited_with(
        "POST",
        "http://localhost:8000/services/deregister",
        json={"service_name": "test_service"},
    )


@pytest.mark.asyncio
async def test_core_services(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: {"test_service": {"name": "test_service"}}
    )

    core = Core.instance(client=client, id="core")
    services = await core.services()

    client.request.assert_awaited_with("GET", "http://localhost:8000/services")
    assert isinstance(services, ServiceCollection)
    assert "name" in services.items
    assert isinstance(services.items["name"], Service)
