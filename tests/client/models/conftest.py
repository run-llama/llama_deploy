from typing import Any, Iterator
from unittest import mock

import pytest

from llama_deploy.client import Client


@pytest.fixture
def client(monkeypatch: Any) -> Iterator[Client]:
    with mock.patch("llama_deploy.client.Client", spec=True):
        c = Client()
        monkeypatch.setattr(c, "request", mock.AsyncMock())
        yield c
