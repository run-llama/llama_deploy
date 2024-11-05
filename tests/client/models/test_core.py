from unittest import mock

import httpx
import pytest
from llama_index.core.workflow import Event

from llama_deploy.client.models.core import (
    Core,
    Service,
    ServiceCollection,
    Session,
    SessionCollection,
)
from llama_deploy.types.core import ServiceDefinition, TaskDefinition, TaskResult


@pytest.mark.asyncio
async def test_session_run(client: mock.AsyncMock) -> None:
    client.request.side_effect = [
        # First call to create task
        mock.MagicMock(json=lambda: "test_task_id"),
        # Second call to get task result, simulate task not done
        mock.MagicMock(json=lambda: None),
        # Third call to get task result, simulate task done
        mock.MagicMock(
            json=lambda: TaskResult(
                task_id="test_task_id", result="test result", history=[]
            ).model_dump()
        ),
    ]

    session = Session(client=client, id="test_session_id")
    result = await session.run("test_service", test_param="test_value")

    assert result == "test result"


@pytest.mark.asyncio
async def test_session_create_task(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(json=lambda: "test_task_id")

    session = Session(client=client, id="test_session_id")
    task_def = TaskDefinition(input="test input", agent_id="test_service")
    task_id = await session.create_task(task_def)

    assert task_id == "test_task_id"


@pytest.mark.asyncio
async def test_session_get_task_result(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: {"task_id": "test_task_id", "result": "test_result", "history": []}
    )

    session = Session(client=client, id="test_session_id")
    result = await session.get_task_result("test_task_id")

    assert result.result == "test_result" if result else ""
    client.request.assert_awaited_with(
        "GET",
        "http://localhost:8000/sessions/test_session_id/tasks/test_task_id/result",
    )


@pytest.mark.asyncio
async def test_service_collection_register(client: mock.AsyncMock) -> None:
    coll = ServiceCollection(client=client, items={})
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
    coll = ServiceCollection(
        client=client,
        items={"test_service": Service(client=client, id="test_service")},
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

    core = Core(client=client, id="core")
    services = await core.services.list()

    client.request.assert_awaited_with("GET", "http://localhost:8000/services")
    assert services[0].id == "test_service"


@pytest.mark.asyncio
async def test_session_collection_create(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(json=lambda: "test_session_id")

    coll = SessionCollection(client=client, items={})
    session = await coll.create()

    client.request.assert_awaited_with("POST", "http://localhost:8000/sessions/create")
    assert isinstance(session, Session)
    assert session.id == "test_session_id"


@pytest.mark.asyncio
async def test_session_collection_get_existing(client: mock.AsyncMock) -> None:
    coll = SessionCollection(client=client, items={})
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

    coll = SessionCollection(client=client, items={})

    with pytest.raises(httpx.HTTPStatusError, match="Not Found"):
        await coll.get("test_session_id")


@pytest.mark.asyncio
async def test_session_collection_get_or_create_existing(
    client: mock.AsyncMock,
) -> None:
    coll = SessionCollection(client=client, items={})
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

    coll = SessionCollection(client=client, items={})
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

    coll = SessionCollection(client=client, items={})
    with pytest.raises(httpx.HTTPStatusError):
        await coll.get_or_create("test_session_id")


@pytest.mark.asyncio
async def test_session_collection_delete(client: mock.AsyncMock) -> None:
    coll = SessionCollection(client=client, items={})
    await coll.delete("test_session_id")

    client.request.assert_awaited_with(
        "POST", "http://localhost:8000/sessions/test_session_id/delete"
    )


@pytest.mark.asyncio
async def test_core_sessions(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: {"test_session": {"id": "test_session"}}
    )

    core = Core(client=client, id="core")
    sessions = await core.sessions.list()

    client.request.assert_awaited_with("GET", "http://localhost:8000/sessions")
    assert sessions[0].id == "test_session"


@pytest.mark.asyncio
async def test_session_get_tasks(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: [
            {
                "input": "task1 input",
                "agent_id": "agent1",
                "session_id": "test_session_id",
            },
            {
                "input": "task2 input",
                "agent_id": "agent2",
                "session_id": "test_session_id",
            },
        ]
    )

    session = Session(client=client, id="test_session_id")
    tasks = await session.get_tasks()

    client.request.assert_awaited_with(
        "GET", "http://localhost:8000/sessions/test_session_id/tasks"
    )
    assert len(tasks) == 2
    assert all(isinstance(task, TaskDefinition) for task in tasks)
    assert tasks[0].input == "task1 input"
    assert tasks[0].agent_id == "agent1"
    assert tasks[0].session_id == "test_session_id"
    assert tasks[1].input == "task2 input"
    assert tasks[1].agent_id == "agent2"
    assert tasks[1].session_id == "test_session_id"


@pytest.mark.asyncio
async def test_session_send_event(client: mock.AsyncMock) -> None:
    event = Event(event_type="test_event", payload={"key": "value"})
    session = Session(client=client, id="test_session_id")

    await session.send_event("test_service", "test_task_id", event)

    client.request.assert_awaited_once_with(
        "POST",
        "http://localhost:8000/sessions/test_session_id/tasks/test_task_id/send_event",
        json={"event_obj_str": mock.ANY, "agent_id": "test_service"},
    )


@pytest.mark.asyncio
async def test_session_run_nowait(client: mock.AsyncMock) -> None:
    client.request.return_value = mock.MagicMock(json=lambda: "test_task_id")

    session = Session(client=client, id="test_session_id")
    task_id = await session.run_nowait("test_service", test_param="test_value")

    assert task_id == "test_task_id"
    client.request.assert_awaited_once_with(
        "POST",
        "http://localhost:8000/sessions/test_session_id/tasks",
        json={
            "input": '{"test_param": "test_value"}',
            "agent_id": "test_service",
            "session_id": "test_session_id",
            "task_id": mock.ANY,
        },
    )
