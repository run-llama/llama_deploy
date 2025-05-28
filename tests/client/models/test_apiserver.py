import io
from typing import Any
from unittest import mock

import httpx
import pytest

from llama_deploy.client.models.apiserver import (
    ApiServer,
    Deployment,
    DeploymentCollection,
    SessionCollection,
    Task,
    TaskCollection,
)
from llama_deploy.types import SessionDefinition, TaskDefinition, TaskResult


@pytest.mark.asyncio
async def test_session_collection_delete(client: Any) -> None:
    coll = SessionCollection(
        client=client,
        items={},
        deployment_id="a_deployment",
    )
    await coll.delete("a_session")
    client.request.assert_awaited_with(
        "POST",
        "http://localhost:4501/deployments/a_deployment/sessions/delete",
        params={"session_id": "a_session"},
        timeout=120.0,
        verify=True,
    )


@pytest.mark.asyncio
async def test_session_collection_create(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: {"session_id": "a_session"}
    )
    coll = SessionCollection(
        client=client,
        items={},
        deployment_id="a_deployment",
    )
    await coll.create()
    client.request.assert_awaited_with(
        "POST",
        "http://localhost:4501/deployments/a_deployment/sessions/create",
        verify=True,
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_session_collection_list(client: Any) -> None:
    # Mock response containing list of sessions
    client.request.return_value = mock.MagicMock(
        json=lambda: [
            SessionDefinition(session_id="session1"),
            SessionDefinition(session_id="session2"),
        ]
    )

    # Create session collection instance
    coll = SessionCollection(
        client=client,
        items={},
        deployment_id="a_deployment",
    )

    # Call list method
    sessions = await coll.list()

    # Verify request was made correctly
    client.request.assert_awaited_with(
        "GET",
        "http://localhost:4501/deployments/a_deployment/sessions",
        verify=True,
        timeout=120.0,
    )

    # Verify returned sessions
    assert len(sessions) == 2
    assert all(isinstance(session, SessionDefinition) for session in sessions)
    assert sessions[0].session_id == "session1"
    assert sessions[1].session_id == "session2"


@pytest.mark.asyncio
async def test_task_results(client: Any) -> None:
    res = TaskResult(task_id="a_result", history=[], result="some_text", data={})
    client.request.return_value = mock.MagicMock(json=lambda: res.model_dump())

    t = Task(
        client=client,
        id="a_task",
        deployment_id="a_deployment",
        session_id="a_session",
    )
    await t.results()

    client.request.assert_awaited_with(
        "GET",
        "http://localhost:4501/deployments/a_deployment/tasks/a_task/results",
        verify=True,
        params={"session_id": "a_session"},
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_collection_run(client: Any) -> None:
    client.request.return_value = mock.MagicMock(json=lambda: "some result")
    coll = TaskCollection(
        client=client,
        items={
            "a_session": Task(
                id="a_session",
                client=client,
                deployment_id="a_deployment",
                session_id="a_session",
            )
        },
        deployment_id="a_deployment",
    )
    await coll.run(TaskDefinition(input="some input", task_id="test_id"))
    client.request.assert_awaited_with(
        "POST",
        "http://localhost:4501/deployments/a_deployment/tasks/run",
        verify=True,
        json={
            "input": "some input",
            "task_id": "test_id",
            "session_id": None,
            "service_id": None,
        },
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_collection_create(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: {"session_id": "a_session", "task_id": "test_id"}
    )
    coll = TaskCollection(
        client=client,
        items={
            "a_session": Task(
                id="a_session",
                client=client,
                deployment_id="a_deployment",
                session_id="a_session",
            )
        },
        deployment_id="a_deployment",
    )
    await coll.create(TaskDefinition(input='{"arg": "test_input"}', task_id="test_id"))
    client.request.assert_awaited_with(
        "POST",
        "http://localhost:4501/deployments/a_deployment/tasks/create",
        verify=True,
        json={
            "input": '{"arg": "test_input"}',
            "task_id": "test_id",
            "session_id": None,
            "service_id": None,
        },
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_deployment_tasks(client: Any) -> None:
    d = Deployment(client=client, id="a_deployment")
    res: list[TaskDefinition] = [
        TaskDefinition(
            input='{"arg": "input"}', task_id="a_task", session_id="a_session"
        )
    ]
    client.request.return_value = mock.MagicMock(json=lambda: res)

    await d.tasks.list()

    client.request.assert_awaited_with(
        "GET",
        "http://localhost:4501/deployments/a_deployment/tasks",
        verify=True,
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_deployment_sessions(client: Any) -> None:
    d = Deployment(client=client, id="a_deployment")
    res: list[SessionDefinition] = [SessionDefinition(session_id="a_session")]
    client.request.return_value = mock.MagicMock(json=lambda: res)

    await d.sessions.list()

    client.request.assert_awaited_with(
        "GET",
        "http://localhost:4501/deployments/a_deployment/sessions",
        verify=True,
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_deployment_collection_create(client: Any) -> None:
    client.request.return_value = mock.MagicMock(json=lambda: {"name": "deployment"})

    coll = DeploymentCollection(client=client, items={})
    await coll.create(io.StringIO("some config"), base_path="tmp")

    client.request.assert_awaited_with(
        "POST",
        "http://localhost:4501/deployments/create",
        files={"config_file": "some config"},
        params={"reload": False, "local": False, "base_path": "tmp"},
        verify=True,
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_deployment_collection_get(client: Any) -> None:
    d = Deployment(client=client, id="a_deployment")
    coll = DeploymentCollection(client=client, items={"a_deployment": d})
    client.request.return_value = mock.MagicMock(json=lambda: {"a_deployment": "Up!"})

    await coll.get("a_deployment")

    client.request.assert_awaited_with(
        "GET",
        "http://localhost:4501/deployments/a_deployment",
        verify=True,
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_status_down(client: Any) -> None:
    client.request.side_effect = httpx.ConnectError(message="connection error")

    apis = ApiServer(client=client, id="apiserver")
    res = await apis.status()

    client.request.assert_awaited_with(
        "GET", "http://localhost:4501/status/", verify=True, timeout=120.0
    )
    assert res.status.value == "Down"


@pytest.mark.asyncio
async def test_status_unhealthy(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        status_code=400, text="This is a drill."
    )

    apis = ApiServer(client=client, id="apiserver")
    res = await apis.status()

    client.request.assert_awaited_with(
        "GET", "http://localhost:4501/status/", verify=True, timeout=120.0
    )
    assert res.status.value == "Unhealthy"
    assert res.status_message == "This is a drill."


@pytest.mark.asyncio
async def test_status_healthy_no_deployments(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        status_code=200, text="", json=lambda: {}
    )

    apis = ApiServer(client=client, id="apiserver")
    res = await apis.status()

    client.request.assert_awaited_with(
        "GET", "http://localhost:4501/status/", verify=True, timeout=120.0
    )
    assert res.status.value == "Healthy"
    assert (
        res.status_message
        == "LlamaDeploy is up and running.\nCurrently there are no active deployments"
    )


@pytest.mark.asyncio
async def test_status_healthy(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        status_code=200, text="", json=lambda: {"deployments": ["foo", "bar"]}
    )

    apis = ApiServer(client=client, id="apiserver")
    res = await apis.status()

    client.request.assert_awaited_with(
        "GET", "http://localhost:4501/status/", verify=True, timeout=120.0
    )
    assert res.status.value == "Healthy"
    assert (
        res.status_message
        == "LlamaDeploy is up and running.\nActive deployments:\n- foo\n- bar"
    )


@pytest.mark.asyncio
async def test_deployments(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        status_code=200, text="", json=lambda: {"deployments": ["foo", "bar"]}
    )
    apis = ApiServer(client=client, id="apiserver")
    await apis.deployments.list()
    client.request.assert_awaited_with("GET", "http://localhost:4501/deployments/")
