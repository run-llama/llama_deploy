from pathlib import Path
from typing import Iterator
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from llama_deploy.apiserver.deployment import Deployment
from llama_deploy.apiserver.config_parser import Config
from llama_deploy.apiserver.app import app


@pytest.fixture
def data_path() -> Path:
    data_p = Path(__file__).parent / "data"
    return data_p.resolve()


@pytest.fixture
def mocked_deployment(data_path: Path) -> Iterator[Deployment]:
    config = Config.from_yaml(data_path / "git_service.yaml")
    with mock.patch("llama_deploy.apiserver.deployment.SOURCE_MANAGERS") as sm_dict:
        sm_dict["git"] = mock.MagicMock()
        yield Deployment(config=config, root_path=Path("."))


@pytest.fixture
def http_client() -> TestClient:
    return TestClient(app)
