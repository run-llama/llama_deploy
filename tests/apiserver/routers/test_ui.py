from __future__ import annotations

from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_manager() -> Generator[MagicMock]:
    """Mock the manager to return a deployment when requested."""
    with patch("llama_deploy.apiserver.routers.ui.manager") as mock_mgr:
        mock_deployment = MagicMock()
        mock_mgr.get_deployment.return_value = mock_deployment
        yield mock_mgr


@pytest.fixture
def mock_httpx_client() -> Generator[AsyncMock]:
    """Mock the httpx AsyncClient."""
    with patch("llama_deploy.apiserver.routers.ui.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_instance


def test_proxy_deployment_not_found(http_client: TestClient) -> None:
    """Test proxy when deployment is not found."""
    with patch(
        "llama_deploy.apiserver.routers.ui.manager.get_deployment", return_value=None
    ):
        response = http_client.get("/ui/nonexistent_deployment/some/path")
        assert response.status_code == 404
        assert response.json()["detail"] == "Deployment not found"


def test_proxy_successful(
    http_client: TestClient, mock_manager: MagicMock, mock_httpx_client: AsyncMock
) -> None:
    """Test successful proxy request."""
    # Mock response content and headers
    mock_content = b"Test content"
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html"}
    mock_response.content = mock_content

    # Set up mock request function
    mock_httpx_client.request.return_value = mock_response

    # Make request to the proxy endpoint
    response = http_client.get("/ui/test_deployment/index.html")

    # Verify the request to the proxied service
    mock_httpx_client.request.assert_called_once()
    args, kwargs = mock_httpx_client.request.call_args
    assert kwargs["method"] == "GET"
    assert kwargs["url"] == "http://localhost:3000/ui/test_deployment/index.html"

    # Verify compression is applied
    assert response.status_code == 200
    assert "content-encoding" in response.headers
    assert response.headers["content-encoding"] == "gzip"
    assert response.content == mock_content


def test_proxy_timeout(
    http_client: TestClient, mock_manager: MagicMock, mock_httpx_client: AsyncMock
) -> None:
    """Test proxy when the proxied service times out."""
    mock_httpx_client.request.side_effect = httpx.TimeoutException("Request timed out")

    response = http_client.get("/ui/test_deployment/index.html")

    # Should return an empty response with 200 status code
    assert response.status_code == 200
    assert response.content == b""
