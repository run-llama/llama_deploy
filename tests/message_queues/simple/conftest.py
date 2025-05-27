import pytest
from fastapi.testclient import TestClient

from llama_deploy.message_queues.simple.server import SimpleMessageQueueServer


@pytest.fixture
def http_client() -> TestClient:
    mqs = SimpleMessageQueueServer()
    return TestClient(mqs._app)
