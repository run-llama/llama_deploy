from pathlib import Path
from typing import Iterator
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from workflows import Workflow, step
from workflows.events import StartEvent, StopEvent

from llama_deploy.apiserver.app import app


class SmallWorkflow(Workflow):
    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        return StopEvent(result="Hello, world!")


@pytest.fixture
def mock_importlib() -> Iterator[None]:
    with mock.patch("llama_deploy.apiserver.deployment.importlib") as importlib:
        importlib.import_module.return_value = mock.MagicMock(
            my_workflow=SmallWorkflow()
        )
        yield


@pytest.fixture
def data_path() -> Path:
    data_p = Path(__file__).parent / "data"
    return data_p.resolve()


@pytest.fixture
def http_client() -> TestClient:
    return TestClient(app)
