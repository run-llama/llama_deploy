import json
import pytest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from llama_deploy.apiserver import Config
from llama_deploy.types import TaskResult

from llama_index.core.workflow import Event


def test_read_deployments(http_client: TestClient) -> None:
    response = http_client.get("/deployments")
    assert response.status_code == 200
    assert response.json() == {"deployments": []}


def test_read_deployment(http_client: TestClient) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        mocked_manager.deployment_names = ["test-deployment"]

        response = http_client.get("/deployments/test-deployment")
        assert response.status_code == 200
        assert response.json() == {"test-deployment": "Up!"}

        response = http_client.get("/deployments/does-not-exist")
        assert response.status_code == 404
        assert response.json() == {"detail": "Deployment not found"}


def test_create_deployment(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        config_file = data_path / "git_service.yaml"

        with open(config_file, "rb") as f:
            actual_config = Config.from_yaml_bytes(f.read())
            response = http_client.post(
                "/deployments/create/",
                files={"config_file": ("git_service.yaml", f, "application/x-yaml")},
            )

        assert response.status_code == 200
        mocked_manager.deploy.assert_called_with(actual_config)


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
        session = mock.AsyncMock()
        deployment.client.get_or_create_session.return_value = session
        session.run.return_value = {"result": "test_result"}
        session.session_id = "42"
        mocked_manager.get_deployment.return_value = deployment
        response = http_client.post(
            "/deployments/test-deployment/tasks/run/",
            json={"input": "{}"},
        )
        assert response.status_code == 200
        deployment.client.delete_session.assert_called_with("42")


def test_create_deployment_task(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"
        session = mock.AsyncMock()
        deployment.client.get_or_create_session.return_value = session
        session.session_id = "42"
        session.run_nowait.return_value = "test_task_id"
        mocked_manager.get_deployment.return_value = deployment
        response = http_client.post(
            "/deployments/test-deployment/tasks/create/",
            json={"input": "{}"},
        )
        assert response.status_code == 200
        assert response.json() == {"session_id": "42", "task_id": "test_task_id"}


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
        deployment.client.get_session.return_value = session
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
        deployment.client.get_session.assert_called_with("42")
        session.get_task_result_stream.assert_called_with("test_task_id")


def test_get_task_result(http_client: TestClient, data_path: Path) -> None:
    with mock.patch(
        "llama_deploy.apiserver.routers.deployments.manager"
    ) as mocked_manager:
        deployment = mock.AsyncMock()
        deployment.default_service = "TestService"
        session = mock.AsyncMock()
        deployment.client.get_session.return_value = session
        session.get_task_result.return_value = TaskResult(
            result="test_result", history=[], task_id="test_task_id"
        )
        mocked_manager.get_deployment.return_value = deployment

        response = http_client.get(
            "/deployments/test-deployment/tasks/test_task_id/results/?session_id=42",
        )
        assert response.status_code == 200
        assert response.json() == "test_result"
        session.get_task_result.assert_called_with("test_task_id")
        deployment.client.get_session.assert_called_with("42")


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
        assert response.json() == {"session_id": "42", "status": "Deleted"}
        deployment.client.delete_session.assert_called_with("42")
