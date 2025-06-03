from __future__ import annotations

from types import TracebackType
from typing import Generator, Optional
from unittest.mock import MagicMock, patch

import pytest
import respx
import httpx
from fastapi.testclient import TestClient


@pytest.fixture
def mock_manager() -> Generator[MagicMock]:
    """Mock the manager to return a deployment when requested."""
    with patch("llama_deploy.apiserver.routers.ui.manager") as mock_mgr:
        mock_deployment = MagicMock()
        mock_mgr.get_deployment.return_value = mock_deployment
        yield mock_mgr


def test_proxy_deployment_not_found(http_client: TestClient) -> None:
    """Test proxy when deployment is not found."""
    with patch(
        "llama_deploy.apiserver.routers.ui.manager.get_deployment", return_value=None
    ):
        response = http_client.get("/ui/nonexistent_deployment/some/path")
        assert response.status_code == 404
        assert response.json()["detail"] == "Deployment not found"


@respx.mock
def test_proxy_successful_html(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test successful proxy request for HTML content."""
    # Mock the upstream server response
    mock_content = b"<html><body>Test content</body></html>"
    respx.get("http://localhost:3000/ui/test_deployment/index.html").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "text/html"}, content=mock_content
        )
    )

    # Make request to the proxy endpoint
    response = http_client.get("/ui/test_deployment/index.html")

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
    respx.get("http://localhost:3000/ui/test_deployment/large.js").mock(
        return_value=httpx.Response(
            200,
            headers={"content-type": "application/javascript"},
            content=mock_content,
        )
    )

    response = http_client.get("/ui/test_deployment/large.js")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/javascript"
    assert response.content == mock_content


@respx.mock
def test_proxy_with_query_params(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test proxy forwards query parameters correctly."""
    mock_content = b'{"result": "success"}'
    respx.get("http://localhost:3000/ui/test_deployment/api").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "application/json"}, content=mock_content
        )
    )

    response = http_client.get("/ui/test_deployment/api?param1=value1&param2=value2")

    assert response.status_code == 200
    # Verify the upstream request included query params
    assert len(respx.calls) == 1
    assert "param1=value1" in str(respx.calls[0].request.url)
    assert "param2=value2" in str(respx.calls[0].request.url)


@respx.mock
def test_proxy_post_with_body(http_client: TestClient, mock_manager: MagicMock) -> None:
    """Test proxy forwards POST requests with body correctly."""
    mock_content = b'{"status": "created"}'
    respx.post("http://localhost:3000/ui/test_deployment/submit").mock(
        return_value=httpx.Response(
            201, headers={"content-type": "application/json"}, content=mock_content
        )
    )

    request_body = {"data": "test"}
    response = http_client.post("/ui/test_deployment/submit", json=request_body)

    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    assert response.content == mock_content


@respx.mock
def test_proxy_header_filtering(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test that hop-by-hop headers are properly filtered."""
    respx.get("http://localhost:3000/ui/test_deployment/test").mock(
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

    response = http_client.get("/ui/test_deployment/test")

    assert response.status_code == 200
    assert "connection" not in response.headers
    assert "transfer-encoding" not in response.headers
    assert response.headers.get("custom-header") == "should-pass-through"


@respx.mock
def test_proxy_redirect_passthrough(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test that redirects are passed through to the client."""
    respx.get("http://localhost:3000/ui/test_deployment/redirect").mock(
        return_value=httpx.Response(
            307, headers={"location": "/ui/test_deployment/new-location"}, content=b""
        )
    )

    response = http_client.get("/ui/test_deployment/redirect", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/ui/test_deployment/new-location"


def test_proxy_connect_error(http_client: TestClient, mock_manager: MagicMock) -> None:
    """Test proxy when upstream server is unavailable."""
    # Don't mock anything - let it fail to connect to localhost:3000
    response = http_client.get("/ui/test_deployment/index.html")

    assert response.status_code == 502
    assert "server unavailable" in response.json()["detail"].lower()


@respx.mock
def test_proxy_path_without_trailing_slash(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test proxy handles paths without trailing slashes correctly."""
    mock_content = b"<html>Home</html>"
    respx.get("http://localhost:3000/ui/test_deployment").mock(
        return_value=httpx.Response(
            200, headers={"content-type": "text/html"}, content=mock_content
        )
    )

    response = http_client.get("/ui/test_deployment")

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
        "llama_deploy.apiserver.routers.ui.manager.get_deployment", return_value=None
    ):
        with pytest.raises(Exception):  # Should close connection
            with http_client.websocket_connect("/ui/nonexistent/ws"):
                pass


def test_websocket_url_construction(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy constructs upstream URL correctly."""
    mock_server = MockWebSocketServer()

    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/ui/test_deployment/chat"):
            pass

        # Verify correct upstream URL was used
        mock_connect.assert_called_once()
        args = mock_connect.call_args[0]
        assert args[0] == "ws://localhost:3000/ui/test_deployment/chat"


def test_websocket_query_params(
    http_client: TestClient, mock_manager: MagicMock
) -> None:
    """Test WebSocket proxy forwards query parameters."""
    mock_server = MockWebSocketServer()

    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/ui/test_deployment/ws?token=abc&room=1"):
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

    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/ui/test_deployment/ws") as websocket:
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

    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/ui/test_deployment/ws") as websocket:
            # Receive messages from upstream via proxy
            msg1 = websocket.receive_text()
            msg2 = websocket.receive_text()

            assert msg1 == "Hello from upstream"
            assert msg2 == "Second message"


def test_websocket_send_bytes(http_client: TestClient, mock_manager: MagicMock) -> None:
    """Test WebSocket proxy forwards binary messages from client to upstream."""
    mock_server = MockWebSocketServer()

    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/ui/test_deployment/ws") as websocket:
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

    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/ui/test_deployment/ws") as websocket:
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

    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.return_value = mock_server

        with http_client.websocket_connect("/ui/test_deployment/ws") as websocket:
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
    with patch("llama_deploy.apiserver.routers.ui.websockets.connect") as mock_connect:
        mock_connect.side_effect = ConnectionError("Cannot connect to upstream")

        # Connection should be established but then closed gracefully
        with http_client.websocket_connect("/ui/test_deployment/ws") as websocket:
            # The connection should close gracefully when upstream fails
            # We can verify this by trying to receive - it should close the connection
            with pytest.raises(Exception):  # Connection will be closed
                websocket.receive_text()
