import json
from pathlib import Path
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from llama_index.core.workflow.context_serializers import JsonSerializer
from llama_index.core.workflow.events import Event, HumanResponseEvent

from llama_deploy.apiserver import DeploymentConfig
from llama_deploy.types import TaskResult
from llama_deploy.types.core import EventDefinition, TaskDefinition


def test_read_deployments(http_client: TestClient) -> None:
    response = http_client.get("/deployments")
    assert response.status_code == 200
    assert response.json() == []


def test_read_deployment(http_client: TestClient) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.deployment_names = ["test-deployment"]

        response = http_client.get("/deployments/test-deployment")
        assert response.status_code == 200
        assert response.json() == {"name": "test-deployment"}

        response = http_client.get("/deployments/does-not-exist")
        assert response.status_code == 404
        assert response.json() == {"detail": "Deployment not found"}


def test_create_deployment(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.deploy = mock.AsyncMock()
        config_file = data_path / "git_service.yaml"

        with open(config_file, "rb") as f:
            actual_config = DeploymentConfig.from_yaml_bytes(f.read())
            response = http_client.post(
                "/deployments/create/",
                files={"config_file": ("git_service.yaml", f, "application/x-yaml")},
            )

        assert response.status_code == 200
        mocked_manager.deploy.assert_awaited_with(actual_config, ".", False, False)


def test_create_deployment_task_not_found(
    http_client: TestClient, data_path: Path
) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.post(
            "/deployments/test-deployment/tasks/create/",
            json={"input": "{}"},
        )
        assert response.status_code == 404


def test_run_task_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.post(
            "/deployments/test-deployment/tasks/run/",
            json={"input": "{}"},
        )
        assert response.status_code == 404


def test_run_task_no_default_service(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = mock.MagicMock(
            default_service=None
        )
        response = http_client.post(
            "/deployments/test-deployment/tasks/run/",
            json={"input": "{}"},
        )
        assert response.status_code == 400


def test_run_task_service_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = mock.MagicMock(
            service_names=["foo"]
        )
        response = http_client.post(
            "/deployments/test-deployment/tasks/run/",
            json={"input": "{}", "service_id": "bar"},
        )
        assert response.status_code == 404


def test_create_deployment_task_missing_service(
    http_client: TestClient, data_path: Path
) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = None
        mocked_manager.get_deployment.return_value = deployment
        response = http_client.post(
            "/deployments/test-deployment/tasks/create/",
            json={"input": "{}"},
        )
        assert response.status_code == 400
        assert (
            response.json().get("detail")
            == "Service is None and deployment has no default service"
        )


def test_run_deployment_task(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"

        session = mock.AsyncMock(id="42")
        deployment.client.core.sessions.create.return_value = session
        session.run.return_value = {"result": "test_result"}

        session_from_get = mock.AsyncMock(id="84")
        deployment.client.core.sessions.get.return_value = session_from_get
        session_from_get.run.return_value = {"result": "test_result_from_existing"}

        mocked_manager.get_deployment.return_value = deployment
        response = http_client.post(
            "/deployments/test-deployment/tasks/run/",
            json={"input": "{}"},
        )
        assert response.status_code == 200
        deployment.client.core.sessions.delete.assert_called_with("42")

        deployment.reset_mock()
        response = http_client.post(
            "/deployments/test-deployment/tasks/run/",
            json={"input": "{}"},
            params={"session_id": 84},
        )
        assert response.status_code == 200
        deployment.client.core.sessions.delete.assert_not_called()


def test_create_deployment_task(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"

        session = mock.AsyncMock(id="42")
        deployment.client.core.sessions.create.return_value = session
        session.run_nowait.return_value = "test_task_id"

        session_from_get = mock.AsyncMock(id="84")
        deployment.client.core.sessions.get.return_value = session_from_get
        session_from_get.run_nowait.return_value = "another_test_task_id"

        mocked_manager.get_deployment.return_value = deployment
        response = http_client.post(
            "/deployments/test-deployment/tasks/create/",
            json={"input": "{}"},
        )
        assert response.status_code == 200
        td = TaskDefinition(**response.json())
        assert td.task_id == "test_task_id"

        deployment.reset_mock()
        response = http_client.post(
            "/deployments/test-deployment/tasks/create/",
            json={"input": "{}"},
            params={"session_id": 84},
        )
        assert response.status_code == 200
        deployment.client.core.sessions.delete.assert_not_called()


def test_send_event_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.post(
            "/deployments/test-deployment/tasks/test_task_id/events",
            json=EventDefinition(service_id="foo", event_obj_str="bar").model_dump(),
            params={"session_id": 42},
        )
        assert response.status_code == 404


def test_send_event(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"
        session = mock.AsyncMock()
        deployment.client.core.sessions.create.return_value = session
        session.id = "42"
        mocked_manager.get_deployment.return_value = deployment

        serializer = JsonSerializer()
        ev = HumanResponseEvent(response="test human response")
        event_def = EventDefinition(
            event_obj_str=serializer.serialize(ev), service_id="TestService"
        )

        response = http_client.post(
            "/deployments/test-deployment/tasks/test_task_id/events",
            json=event_def.model_dump(),
            params={"session_id": 42},
        )
        assert response.status_code == 200
        ev_def = EventDefinition(**response.json())
        assert ev_def.service_id == event_def.service_id
        assert ev_def.event_obj_str == event_def.event_obj_str


def test_get_event_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.get(
            "/deployments/test-deployment/tasks/test_task_id/events",
            params={"session_id": "42", "task_id": "84"},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_event_stream(http_client: TestClient, data_path: Path) -> None:
    mock_events = [
        Event(msg="mock event 1"),
        Event(msg="mock event 2"),
        Event(msg="mock event 3"),
    ]

    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"
        session = mock.MagicMock()
        deployment.client.core.sessions.get.return_value = session
        mocked_manager.get_deployment.return_value = deployment
        mocked_get_task_result_stream = mock.MagicMock()
        mocked_get_task_result_stream.__aiter__.return_value = (
            ev.dict() for ev in mock_events
        )
        session.get_task_result_stream.return_value = mocked_get_task_result_stream

        response = http_client.get(
            "/deployments/test-deployment/tasks/test_task_id/events/?session_id=42",
        )
        assert response.status_code == 200
        ix = 0
        async for line in response.aiter_lines():
            data = json.loads(line)
            assert data == mock_events[ix].dict()
            ix += 1
        deployment.client.core.sessions.get.assert_called_with("42")
        session.get_task_result_stream.assert_called_with("test_task_id")


def test_get_task_result_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.get(
            "/deployments/test-deployment/tasks/test_task_id/results/?session_id=42",
        )
        assert response.status_code == 404


def test_get_tasks_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.get(
            "/deployments/test-deployment/tasks",
        )
        assert response.status_code == 404


def test_get_tasks(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        mocked_manager.get_deployment.return_value = deployment
        session = mock.AsyncMock()
        session.get_tasks.return_value = [TaskDefinition(input="foo")]
        deployment.client.core.sessions.list.return_value = [session]

        response = http_client.get(
            "/deployments/test-deployment/tasks",
        )
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["input"] == "foo"


def test_get_task_result(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"
        session = mock.AsyncMock()
        deployment.client.core.sessions.get.return_value = session
        session.get_task_result.return_value = TaskResult(
            result="test_result", history=[], task_id="test_task_id"
        )
        mocked_manager.get_deployment.return_value = deployment

        response = http_client.get(
            "/deployments/test-deployment/tasks/test_task_id/results/?session_id=42",
        )
        assert response.status_code == 200
        assert TaskResult(**response.json()).result == "test_result"
        session.get_task_result.assert_called_with("test_task_id")
        deployment.client.core.sessions.get.assert_called_with("42")


def test_get_sessions_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.get(
            "/deployments/test-deployment/sessions/",
        )
        assert response.status_code == 404


def test_get_sessions(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"
        deployment.client.list_sessions.return_value = []
        mocked_manager.get_deployment.return_value = deployment

        response = http_client.get(
            "/deployments/test-deployment/sessions/",
        )
        assert response.status_code == 200
        assert response.json() == []


def test_delete_session_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.post(
            "/deployments/test-deployment/sessions/delete/?session_id=42",
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Deployment not found"}


def test_delete_session(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"
        mocked_manager.get_deployment.return_value = deployment

        response = http_client.post(
            "/deployments/test-deployment/sessions/delete/?session_id=42",
        )
        assert response.status_code == 200
        deployment.client.core.sessions.delete.assert_called_with("42")


def test_get_session_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.get(
            "/deployments/test-deployment/sessions/foo",
        )
        assert response.status_code == 404


def test_get_session(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        mocked_manager.get_deployment.return_value = deployment
        session = mock.AsyncMock(id="foo")
        deployment.client.core.sessions.get.return_value = session
        response = http_client.get("/deployments/test-deployment/sessions/foo")
        assert response.status_code == 200
        assert response.json() == {"session_id": "foo", "state": {}, "task_ids": []}


def test_create_session_not_found(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.get_deployment.return_value = None
        response = http_client.post(
            "/deployments/test-deployment/sessions/create",
        )

        assert response.status_code == 404


def test_create_session(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        session = mock.AsyncMock(id="test-session-id")
        deployment.client.core.sessions.create.return_value = session
        mocked_manager.get_deployment.return_value = deployment

        response = http_client.post(
            "/deployments/test-deployment/sessions/create",
        )

        assert response.status_code == 200
        assert response.json() == {
            "session_id": "test-session-id",
            "state": {},
            "task_ids": [],
        }

        # Verify the mocked calls
        mocked_manager.get_deployment.assert_called_once_with("test-deployment")
        deployment.client.core.sessions.create.assert_called_once()
