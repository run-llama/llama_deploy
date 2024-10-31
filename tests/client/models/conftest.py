from typing import Any, Iterator
from unittest import mock

import pytest

from llama_deploy.client import Client


@pytest.fixture
def client(monkeypatch: Any) -> Iterator[Client]:
    monkeypatch.setattr(Client, "request", mock.AsyncMock())
    yield Client()
