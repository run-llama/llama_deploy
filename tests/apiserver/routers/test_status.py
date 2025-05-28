from typing import Any
from unittest import mock

import httpx
from fastapi.testclient import TestClient

from llama_deploy.apiserver import settings


def test_read_main(http_client: TestClient) -> None:
    response = http_client.get("/status")
    assert response.status_code == 200
    assert response.json() == {
        "max_deployments": 10,
        "deployments": [],
        "status": "Healthy",
        "status_message": "",
    }


def test_prom_proxy_off(http_client: TestClient, monkeypatch: Any) -> None:
    monkeypatch.setattr(settings, "prometheus_enabled", False)
    response = http_client.get("/status/metrics/")
    assert response.status_code == 204
    assert response.text == ""


def test_prom_proxy(http_client: TestClient) -> None:
    mock_metrics_response = 'metric1{label="value"} 1.0\nmetric2{label="value"} 2.0'
    mock_response = httpx.Response(200, text=mock_metrics_response)

    with mock.patch("httpx.AsyncClient.get", return_value=mock_response):
        response = http_client.get("/status/metrics")
        assert response.status_code == 200
        assert response.text == mock_metrics_response


def test_prom_proxy_failure(http_client: TestClient) -> None:
    # Mock the HTTP client to raise an exception
    with mock.patch(
        "httpx.AsyncClient.get", side_effect=httpx.RequestError("Connection failed")
    ):
        response = http_client.get("/status/metrics")
        assert response.status_code == 500
        assert response.json()["detail"] == "Connection failed"
