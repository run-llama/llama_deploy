from unittest import mock

import httpx
import pytest

from llama_deploy.client.models.core import (
    Core,
    Service,
    ServiceCollection,
    Session,
    SessionCollection,
)
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
    coll = ServiceCollection.instance(
        client=client,
        items={"test_service": Service.instance(client=client, id="test_service")},
    )
    await coll.deregister("test_service")

    client.request.assert_awaited_with(
        "POST",
        "http://localhost:8000/services/deregister",
        params={"service_name": "test_service"},
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
    assert "test_service" in services.items
    assert isinstance(services.items["test_service"], Service)


@pytest.mark.asyncio
async def test_session_collection_create(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(json=lambda: "test_session_id")

    coll = SessionCollection.instance(client=client, items={})
    session = await coll.create()

    client.request.assert_awaited_with("POST", "http://localhost:8000/sessions/create")
    assert isinstance(session, Session)
    assert session.id == "test_session_id"


@pytest.mark.asyncio
async def test_session_collection_get_existing(client: mock.AsyncMock) -> None:
    coll = SessionCollection.instance(client=client, items={})
    session = await coll.get("test_session_id")

    client.request.assert_awaited_with(
        "GET", "http://localhost:8000/sessions/test_session_id"
    )
    assert isinstance(session, Session)
    assert session.id == "test_session_id"


@pytest.mark.asyncio
async def test_session_collection_get_nonexistent(client: mock.AsyncMock) -> None:
    client.request.side_effect = httpx.HTTPStatusError(
        "Not Found", request=mock.MagicMock(), response=mock.MagicMock(status_code=404)
    )

    coll = SessionCollection.instance(client=client, items={})

    with pytest.raises(httpx.HTTPStatusError, match="Not Found"):
        await coll.get("test_session_id")


@pytest.mark.asyncio
async def test_session_collection_get_or_create_existing(
    client: mock.AsyncMock,
) -> None:
    coll = SessionCollection.instance(client=client, items={})
    session = await coll.get_or_create("test_session_id")

    client.request.assert_awaited_with(
        "GET", "http://localhost:8000/sessions/test_session_id"
    )
    assert isinstance(session, Session)
    assert session.id == "test_session_id"


@pytest.mark.asyncio
async def test_session_collection_get_or_create_nonexistent(
    client: mock.AsyncMock,
) -> None:
    client.request.side_effect = [
        httpx.HTTPStatusError(
            "Not Found",
            request=mock.MagicMock(),
            response=mock.MagicMock(status_code=404),
        ),
        mock.MagicMock(json=lambda: "test_session_id"),
    ]

    coll = SessionCollection.instance(client=client, items={})
    await coll.get_or_create("test_session_id")
    client.request.assert_awaited_with("POST", "http://localhost:8000/sessions/create")


@pytest.mark.asyncio
async def test_session_collection_get_or_create_error(
    client: mock.AsyncMock,
) -> None:
    client.request.side_effect = [
        httpx.HTTPStatusError(
            "Not Available",
            request=mock.MagicMock(),
            response=mock.MagicMock(status_code=503),
        )
    ]

    coll = SessionCollection.instance(client=client, items={})
    with pytest.raises(httpx.HTTPStatusError):
        await coll.get_or_create("test_session_id")


@pytest.mark.asyncio
async def test_session_collection_delete(client: mock.AsyncMock) -> None:
    coll = SessionCollection.instance(client=client, items={})
    await coll.delete("test_session_id")

    client.request.assert_awaited_with(
        "POST", "http://localhost:8000/sessions/test_session_id/delete"
    )


@pytest.mark.asyncio
async def test_core_sessions(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: {"test_session": {"id": "test_session"}}
    )

    core = Core.instance(client=client, id="core")
    sessions = await core.sessions()

    client.request.assert_awaited_with("GET", "http://localhost:8000/sessions")
    assert isinstance(sessions, SessionCollection)
    assert "test_session" in sessions.items
    assert isinstance(sessions.items["test_session"], Session)
