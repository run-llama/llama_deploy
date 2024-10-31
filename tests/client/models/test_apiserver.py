import io
from typing import Any
from unittest import mock

import httpx
import pytest

from llama_deploy.client.models.apiserver import (
    ApiServer,
    Deployment,
    DeploymentCollection,
    Session,
    SessionCollection,
    Task,
    TaskCollection,
)
from llama_deploy.types import SessionDefinition, TaskDefinition, TaskResult


@pytest.mark.asyncio
async def test_session_collection_delete(client: Any) -> None:
    coll = SessionCollection.instance(
        client=client,
        items={"a_session": Session.instance(id="a_session", client=client)},
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
    coll = SessionCollection.instance(
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
async def test_task_results(client: Any) -> None:
    res = TaskResult(task_id="a_result", history=[], result="some_text", data={})
    client.request.return_value = mock.MagicMock(json=lambda: res.model_dump_json())

    t = Task.instance(
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
    coll = TaskCollection.instance(
        client=client,
        items={
            "a_session": Task.instance(
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
            "agent_id": None,
        },
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_collection_create(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        json=lambda: {"session_id": "a_session", "task_id": "test_id"}
    )
    coll = TaskCollection.instance(
        client=client,
        items={
            "a_session": Task.instance(
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
            "agent_id": None,
        },
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_deployment_tasks(client: Any) -> None:
    d = Deployment.instance(client=client, id="a_deployment")
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
    d = Deployment.instance(client=client, id="a_deployment")
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

    coll = DeploymentCollection.instance(client=client, items={})
    await coll.create(io.StringIO("some config"))

    client.request.assert_awaited_with(
        "POST",
        "http://localhost:4501/deployments/create",
        files={"config_file": "some config"},
        verify=True,
        timeout=120.0,
    )


@pytest.mark.asyncio
async def test_task_deployment_collection_get(client: Any) -> None:
    d = Deployment.instance(client=client, id="a_deployment")
    coll = DeploymentCollection.instance(client=client, items={"a_deployment": d})
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

    apis = ApiServer.instance(client=client, id="apiserver")
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

    apis = ApiServer.instance(client=client, id="apiserver")
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

    apis = ApiServer.instance(client=client, id="apiserver")
    res = await apis.status()

    client.request.assert_awaited_with(
        "GET", "http://localhost:4501/status/", verify=True, timeout=120.0
    )
    assert res.status.value == "Healthy"
    assert (
        res.status_message
        == "Llama Deploy is up and running.\nCurrently there are no active deployments"
    )


@pytest.mark.asyncio
async def test_status_healthy(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        status_code=200, text="", json=lambda: {"deployments": ["foo", "bar"]}
    )

    apis = ApiServer.instance(client=client, id="apiserver")
    res = await apis.status()

    client.request.assert_awaited_with(
        "GET", "http://localhost:4501/status/", verify=True, timeout=120.0
    )
    assert res.status.value == "Healthy"
    assert (
        res.status_message
        == "Llama Deploy is up and running.\nActive deployments:\n- foo\n- bar"
    )


@pytest.mark.asyncio
async def test_deployments(client: Any) -> None:
    client.request.return_value = mock.MagicMock(
        status_code=200, text="", json=lambda: {"deployments": ["foo", "bar"]}
    )
    apis = ApiServer.instance(client=client, id="apiserver")
    await apis.deployments.list()
    client.request.assert_awaited_with(
        "GET", "http://localhost:4501/deployments/", verify=True, timeout=120.0
    )
