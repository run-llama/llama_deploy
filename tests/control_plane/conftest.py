from typing import Any
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from llama_deploy.control_plane.server import ControlPlaneConfig, ControlPlaneServer


@pytest.fixture
def kvstore() -> Any:
    with mock.patch(
        "llama_deploy.control_plane.server.SimpleKVStore"
    ) as mocked_kvstore:
        mock_instance = mock.AsyncMock()
        mocked_kvstore.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def http_client(kvstore: Any) -> TestClient:
    server = ControlPlaneServer(
        message_queue=mock.AsyncMock(), config=ControlPlaneConfig(cors_origins=["*"])
    )
    return TestClient(server.app)
