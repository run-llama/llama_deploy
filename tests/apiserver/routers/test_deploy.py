from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from llama_deploy.apiserver import Config


def test_read_deployments(http_client: TestClient) -> None:
    response = http_client.get("/deployments")
    assert response.status_code == 200
    assert response.json() == {"deployments": []}


def test_read_deployment(http_client: TestClient) -> None:
    with mock.patch("llama_deploy.apiserver.routers.deploy.manager") as mocked_manager:
        mocked_manager.deployment_names = ["test-deployment"]

        response = http_client.get("/deployments/test-deployment")
        assert response.status_code == 200
        assert response.json() == {"test-deployment": "Up!"}

        response = http_client.get("/deployments/does-not-exist")
        assert response.status_code == 404
        assert response.json() == {"detail": "Deployment not found"}


def test_create_deployment(http_client: TestClient, data_path: Path) -> None:
    with mock.patch("llama_deploy.apiserver.routers.deploy.manager") as mocked_manager:
        config_file = data_path / "git_service.yaml"

        with open(config_file, "rb") as f:
            actual_config = Config.from_yaml_bytes(f.read())
            response = http_client.post(
                "/deployments/create/",
                files={"config_file": ("git_service.yaml", f, "application/x-yaml")},
            )

        assert response.status_code == 200
        mocked_manager.deploy.assert_called_with(actual_config)
