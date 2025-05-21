from pathlib import Path
from typing import Any, Iterator
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from llama_index.core.workflow import Workflow

from llama_deploy.apiserver.app import app
from llama_deploy.apiserver.deployment import Deployment
from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig


@pytest.fixture
def mock_importlib() -> Iterator[None]:
    with mock.patch("llama_deploy.apiserver.deployment.importlib") as importlib:
        importlib.import_module.return_value = mock.MagicMock(my_workflow=Workflow())
        yield


@pytest.fixture
def data_path() -> Path:
    data_p = Path(__file__).parent / "data"
    return data_p.resolve()


@pytest.fixture
def mocked_deployment(data_path: Path, mock_importlib: Any) -> Iterator[Deployment]:
    config = DeploymentConfig.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        yield Deployment(config=config, base_path=data_path, deployment_path=Path("."))


@pytest.fixture
def http_client() -> TestClient:
    return TestClient(app)
