from __future__ import annotations

import json
from pathlib import Path
from types import TracebackType
from typing import Generator, Optional
from unittest import mock
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from llama_index.core.workflow.context_serializers import JsonSerializer
from llama_index.core.workflow.events import Event

from llama_deploy.apiserver import DeploymentConfig
from llama_deploy.types import TaskResult
from llama_deploy.types.core import EventDefinition, TaskDefinition


@pytest.fixture
def mock_manager() -> Generator[MagicMock]:
    """Mock the manager to return a deployment when requested."""
    with patch("llama_deploy.apiserver.routers.deployments.manager") as mock_mgr:
        mock_deployment = MagicMock()
        mock_mgr.get_deployment.return_value = mock_deployment
        yield mock_mgr


def test_read_deployments(http_client: TestClient) -> None:
    response = http_client.get("/deployments")
    assert response.status_code == 200
    assert response.json() == []


def test_read_deployment(http_client: TestClient, mock_manager: MagicMock) -> None:
    mock_manager.deployment_names = ["test-deployment"]

    response = http_client.get("/deployments/test-deployment")
    assert response.status_code == 200
    assert response.json() == {"name": "test-deployment"}

    response = http_client.get("/deployments/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"detail": "Deployment not found"}


def test_create_deployment(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.deploy = mock.AsyncMock()
    config_file = data_path / "git_service.yaml"

    with open(config_file, "rb") as f:
        actual_config = DeploymentConfig.from_yaml_bytes(f.read())
        response = http_client.post(
            "/deployments/create/",
            files={"config_file": ("git_service.yaml", f, "application/x-yaml")},
        )

    assert response.status_code == 200
    mock_manager.deploy.assert_awaited_with(actual_config, ".", False, False)


def test_create_deployment_task_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.post(
        "/deployments/test-deployment/tasks/create/",
        json={"input": "{}"},
    )
    assert response.status_code == 404


def test_run_task_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.post(
        "/deployments/test-deployment/tasks/run/",
        json={"input": "{}"},
    )
    assert response.status_code == 404


def test_run_task_no_default_service(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = mock.MagicMock(default_service=None)
    response = http_client.post(
        "/deployments/test-deployment/tasks/run/",
        json={"input": "{}"},
    )
    assert response.status_code == 400


def test_run_task_service_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = mock.MagicMock(service_names=["foo"])
    response = http_client.post(
        "/deployments/test-deployment/tasks/run/",
        json={"input": "{}", "service_id": "bar"},
    )
    assert response.status_code == 404


def test_create_deployment_task_missing_service(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    deployment.default_service = None
    mock_manager.get_deployment.return_value = deployment
    response = http_client.post(
        "/deployments/test-deployment/tasks/create/",
        json={"input": "{}"},
    )
    assert response.status_code == 400
    assert (
        response.json().get("detail")
        == "Service is None and deployment has no default service"
    )


def test_run_deployment_task(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    deployment.default_service = "TestService"

    session = mock.AsyncMock(id="42")
    deployment.client.core.sessions.create.return_value = session
    session.run.return_value = {"result": "test_result"}

    session_from_get = mock.AsyncMock(id="84")
    deployment.client.core.sessions.get.return_value = session_from_get
    session_from_get.run.return_value = {"result": "test_result_from_existing"}

    mock_manager.get_deployment.return_value = deployment
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


def test_create_deployment_task(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    deployment.default_service = "TestService"

    session = mock.AsyncMock(id="42")
    deployment.client.core.sessions.create.return_value = session
    session.run_nowait.return_value = "test_task_id"

    session_from_get = mock.AsyncMock(id="84")
    deployment.client.core.sessions.get.return_value = session_from_get
    session_from_get.run_nowait.return_value = "another_test_task_id"

    mock_manager.get_deployment.return_value = deployment
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


def test_send_event_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.post(
        "/deployments/test-deployment/tasks/test_task_id/events",
        json=EventDefinition(service_id="foo", event_obj_str="bar").model_dump(),
        params={"session_id": 42},
    )
    assert response.status_code == 404


class SomeEvent(Event):
    response: str


def test_send_event(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    deployment.default_service = "TestService"
    session = mock.AsyncMock()
    deployment.client.core.sessions.create.return_value = session
    session.id = "42"
    mock_manager.get_deployment.return_value = deployment

    serializer = JsonSerializer()
    ev = SomeEvent(response="test human response")
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


def test_get_event_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.get(
        "/deployments/test-deployment/tasks/test_task_id/events",
        params={"session_id": "42", "task_id": "84"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_event_stream(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_events = [
        Event(msg="mock event 1"),
        Event(msg="mock event 2"),
        Event(msg="mock event 3"),
    ]

    deployment = mock.AsyncMock()
    deployment.default_service = "TestService"
    session = mock.MagicMock()
    deployment.client.core.sessions.get.return_value = session
    mock_manager.get_deployment.return_value = deployment
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


def test_get_task_result_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.get(
        "/deployments/test-deployment/tasks/test_task_id/results/?session_id=42",
    )
    assert response.status_code == 404


def test_get_tasks_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.get(
        "/deployments/test-deployment/tasks",
    )
    assert response.status_code == 404


def test_get_tasks(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    mock_manager.get_deployment.return_value = deployment
    session = mock.AsyncMock()
    session.get_tasks.return_value = [TaskDefinition(input="foo")]
    deployment.client.core.sessions.list.return_value = [session]

    response = http_client.get(
        "/deployments/test-deployment/tasks",
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["input"] == "foo"


def test_get_task_result(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    deployment.default_service = "TestService"
    session = mock.AsyncMock()
    deployment.client.core.sessions.get.return_value = session
    session.get_task_result.return_value = TaskResult(
        result="test_result", history=[], task_id="test_task_id"
    )
    mock_manager.get_deployment.return_value = deployment

    response = http_client.get(
        "/deployments/test-deployment/tasks/test_task_id/results/?session_id=42",
    )
    assert response.status_code == 200
    assert TaskResult(**response.json()).result == "test_result"
    session.get_task_result.assert_called_with("test_task_id")
    deployment.client.core.sessions.get.assert_called_with("42")


def test_get_sessions_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.get(
        "/deployments/test-deployment/sessions/",
    )
    assert response.status_code == 404


def test_get_sessions(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    deployment.default_service = "TestService"
    deployment.client.list_sessions.return_value = []
    mock_manager.get_deployment.return_value = deployment

    response = http_client.get(
        "/deployments/test-deployment/sessions/",
    )
    assert response.status_code == 200
    assert response.json() == []


def test_delete_session_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.post(
        "/deployments/test-deployment/sessions/delete/?session_id=42",
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Deployment not found"}


def test_delete_session(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    deployment.default_service = "TestService"
    mock_manager.get_deployment.return_value = deployment

    response = http_client.post(
        "/deployments/test-deployment/sessions/delete/?session_id=42",
    )
    assert response.status_code == 200
    deployment.client.core.sessions.delete.assert_called_with("42")


def test_get_session_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.get(
        "/deployments/test-deployment/sessions/foo",
    )
    assert response.status_code == 404


def test_get_session(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    mock_manager.get_deployment.return_value = deployment
    session = mock.AsyncMock(id="foo")
    deployment.client.core.sessions.get.return_value = session
    response = http_client.get("/deployments/test-deployment/sessions/foo")
    assert response.status_code == 200
    assert response.json() == {"session_id": "foo", "state": {}, "task_ids": []}


def test_create_session_not_found(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    mock_manager.get_deployment.return_value = None
    response = http_client.post(
        "/deployments/test-deployment/sessions/create",
    )

    assert response.status_code == 404


def test_create_session(
    http_client: TestClient, data_path: Path, mock_manager: MagicMock
) -> None:
    deployment = mock.AsyncMock()
    session = mock.AsyncMock(id="test-session-id")
    deployment.client.core.sessions.create.return_value = session
    mock_manager.get_deployment.return_value = deployment

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
    mock_manager.get_deployment.assert_called_once_with("test-deployment")
    deployment.client.core.sessions.create.assert_called_once()


@respx.mock
def test_proxy_successful_html(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test successful proxy request for HTML content."""
    # Mock the upstream server response
    mock_content = b"<html><body>Test content</body></html>"
    respx.get("http://localhost:3000/deployments/test_deployment/ui/index.html").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "text/html"}, content=mock_content
        )
    )

    # Make request to the proxy endpoint
    response = http_client.get("/deployments/test_deployment/ui/index.html")

    # Verify the response
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html"
    assert response.content == mock_content


@respx.mock
def test_proxy_successful_streaming_content(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test successful proxy request with streaming content."""
    # Mock a larger response that would benefit from streaming
    mock_content = b"x" * 10000  # 10KB content
    respx.get("http://localhost:3000/deployments/test_deployment/ui/large.js").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/javascript"},
            content=mock_content,
        )
    )

    response = http_client.get("/deployments/test_deployment/ui/large.js")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/javascript"
    assert response.content == mock_content


@respx.mock
def test_proxy_with_query_params(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test proxy forwards query parameters correctly."""
    mock_content = b'{"result": "success"}'
    respx.get("http://localhost:3000/deployments/test_deployment/ui/api").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "application/json"}, content=mock_content
        )
    )

    response = http_client.get(
        "/deployments/test_deployment/ui/api?param1=value1&param2=value2"
    )

    assert response.status_code == 200
    # Verify the upstream request included query params
    assert len(respx.calls) == 1
    assert "param1=value1" in str(respx.calls[0].request.url)
    assert "param2=value2" in str(respx.calls[0].request.url)


@respx.mock
def test_proxy_post_with_body(http_client: TestClient, mock_manager: MagicMock) -> None:
    """Test proxy forwards POST requests with body correctly."""
    mock_content = b'{"status": "created"}'
    respx.post("http://localhost:3000/deployments/test_deployment/ui/submit").mock(
        return_value=httpx.Response(
            201, headers={"content-type": "application/json"}, content=mock_content
        )
    )

    request_body = {"data": "test"}
    response = http_client.post(
        "/deployments/test_deployment/ui/submit", json=request_body
    )

    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    assert response.content == mock_content


@respx.mock
def test_proxy_header_filtering(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test that hop-by-hop headers are properly filtered."""
    respx.get("http://localhost:3000/deployments/test_deployment/ui/test").mock(
        return_value=httpx.Response(
            200,
            headers={
                "content-type": "text/html",
                "connection": "keep-alive",  # should be filtered
                "transfer-encoding": "chunked",  # should be filtered
                "custom-header": "should-pass-through",  # should pass through
            },
            content=b"test content",
        )
    )

    response = http_client.get("/deployments/test_deployment/ui/test")

    assert response.status_code == 200
    assert "connection" not in response.headers
    assert "transfer-encoding" not in response.headers
    assert response.headers.get("custom-header") == "should-pass-through"


@respx.mock
def test_proxy_redirect_passthrough(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test that redirects are passed through to the client."""
    respx.get("http://localhost:3000/deployments/test_deployment/ui/redirect").mock(
        return_value=httpx.Response(
            307,
            headers={"location": "/deployments/test_deployment/ui/new-location"},
            content=b"",
        )
    )

    response = http_client.get(
        "/deployments/test_deployment/ui/redirect", follow_redirects=False
    )

    assert response.status_code == 307
    assert (
        response.headers["location"] == "/deployments/test_deployment/ui/new-location"
    )


def test_proxy_connect_error(http_client: TestClient, mock_manager: MagicMock) -> None:
    """Test proxy when upstream server is unavailable."""
    # Don't mock anything - let it fail to connect to localhost:3000
    response = http_client.get("/deployments/test_deployment/ui/index.html")

    assert response.status_code == 502
    assert "server unavailable" in response.json()["detail"].lower()


@respx.mock
def test_proxy_path_without_trailing_slash(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test proxy handles paths without trailing slashes correctly."""
    mock_content = b"<html>Home</html>"
    respx.get("http://localhost:3000/deployments/test_deployment/ui").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "text/html"}, content=mock_content
        )
    )

    response = http_client.get("/deployments/test_deployment/ui")

    assert response.status_code == 200
    assert response.content == mock_content


# WebSocket Tests - Simplified approach


class MockWebSocketServer:
    """Simple mock WebSocket server for testing."""

    def __init__(self, messages_to_send: list[str | bytes] | None = None) -> None:
        self.messages_to_send = messages_to_send or []
        self.received_messages: list[str | bytes] = []
        self.connected_url: Optional[str] = None
        self.headers: dict[str, str] = {}
        self.subprotocols: list[str] = []

    async def __aenter__(self) -> MockWebSocketServer:
        return self

    async def __aexit__(
        self, exc_type: type, exc_val: Exception, exc_tb: TracebackType
    ) -> None:
        pass

    async def send(self, message: str | bytes) -> None:
        self.received_messages.append(message)

    async def close(self, code: int = 1000) -> None:
        pass

    def __aiter__(self) -> MockWebSocketServer:
        return self

    async def __anext__(self) -> str | bytes:
        if self.messages_to_send:
            return self.messages_to_send.pop(0)
        raise StopAsyncIteration


def test_websocket_deployment_not_found(http_client: TestClient) -> None:
    """Test WebSocket proxy when deployment is not found."""
    with patch(
        "llama_deploy.apiserver.routers.deployments.manager.get_deployment",
        return_value=None,
    ):
        with pytest.raises(Exception):  # Should close connection
            with http_client.websocket_connect("/deployments/ui/nonexistent/ws"):
                pass


def test_websocket_url_construction(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy constructs upstream URL correctly."""
    mock_server = MockWebSocketServer()

    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/deployments/test_deployment/ui/chat"):
            pass

        # Verify correct upstream URL was used
        mock_connect.assert_called_once()
        args = mock_connect.call_args[0]
        assert args[0] == "ws://localhost:3000/deployments/test_deployment/ui/chat"


def test_websocket_query_params(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy forwards query parameters."""
    mock_server = MockWebSocketServer()

    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect(
            "/deployments/test_deployment/ui/ws?token=abc&room=1"
        ):
            pass

        # Verify query params in upstream URL
        upstream_url = mock_connect.call_args[0][0]
        assert "token=abc" in upstream_url
        assert "room=1" in upstream_url


def test_websocket_message_forwarding(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy forwards messages correctly."""
    mock_server = MockWebSocketServer()

    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect(
            "/deployments/test_deployment/ui/ws"
        ) as websocket:
            websocket.send_text("hello upstream")

        # Verify message was forwarded to mock upstream
        assert "hello upstream" in mock_server.received_messages


def test_websocket_receive_text(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy forwards text messages from upstream to client."""
    # Mock server will send these messages to the client
    mock_server = MockWebSocketServer(
        messages_to_send=["Hello from upstream", "Second message"]
    )

    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect(
            "/deployments/test_deployment/ui/ws"
        ) as websocket:
            # Receive messages from upstream via proxy
            msg1 = websocket.receive_text()
            msg2 = websocket.receive_text()

            assert msg1 == "Hello from upstream"
            assert msg2 == "Second message"


def test_websocket_send_bytes(http_client: TestClient, mock_manager: MagicMock) -> None:
    """Test WebSocket proxy forwards binary messages from client to upstream."""
    mock_server = MockWebSocketServer()

    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect(
            "/deployments/test_deployment/ui/ws"
        ) as websocket:
            binary_data = b"binary data from client"
            websocket.send_bytes(binary_data)

        # Verify binary data was forwarded to mock upstream
        assert binary_data in mock_server.received_messages


def test_websocket_receive_bytes(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy forwards binary messages from upstream to client."""
    # Mock server will send binary data to the client
    binary_data = b"binary data from upstream"
    mock_server = MockWebSocketServer(messages_to_send=[binary_data])

    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect(
            "/deployments/test_deployment/ui/ws"
        ) as websocket:
            # Receive binary data from upstream via proxy
            received_data = websocket.receive_bytes()

            assert received_data == binary_data


def test_websocket_mixed_message_types(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy handles mixed text and binary messages correctly."""
    # Mix of text and binary messages from upstream
    messages: list[str | bytes] = ["text message", b"binary message", "another text"]
    mock_server = MockWebSocketServer(messages_to_send=messages)

    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect(
            "/deployments/test_deployment/ui/ws"
        ) as websocket:
            # Send mixed types to upstream
            websocket.send_text("client text")
            websocket.send_bytes(b"client binary")

            # Receive mixed types from upstream
            msg1 = websocket.receive_text()
            msg2 = websocket.receive_bytes()
            msg3 = websocket.receive_text()

            assert msg1 == "text message"
            assert msg2 == b"binary message"
            assert msg3 == "another text"

        # Verify client messages were forwarded
        assert "client text" in mock_server.received_messages
        assert b"client binary" in mock_server.received_messages


def test_websocket_connection_error(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy handles connection errors gracefully."""
    with patch(
        "llama_deploy.apiserver.routers.deployments.websockets.connect"
    ) as mock_connect:
        mock_connect.side_effect = ConnectionError("Cannot connect to upstream")

        # Connection should be established but then closed gracefully
        with http_client.websocket_connect(
            "/deployments/test_deployment/ui/ws"
        ) as websocket:
            # The connection should close gracefully when upstream fails
            # We can verify this by trying to receive - it should close the connection
            with pytest.raises(Exception):  # Connection will be closed
                websocket.receive_text()
