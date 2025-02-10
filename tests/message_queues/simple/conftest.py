import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import PrivateAttr

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.simple.server import SimpleMessageQueueServer
from llama_deploy.messages.base import QueueMessage


class MockMessageConsumer(BaseMessageQueueConsumer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    processed_messages: list[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.fixture
def http_client() -> TestClient:
    mqs = SimpleMessageQueueServer()
    return TestClient(mqs._app)
