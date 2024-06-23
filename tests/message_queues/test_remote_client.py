import asyncio
import pytest
from fastapi.testclient import TestClient
from pydantic import PrivateAttr
from typing import Any, Callable, Dict, List, TYPE_CHECKING
from urllib.parse import urlsplit
from unittest.mock import patch, MagicMock
from agentfile.messages.base import QueueMessage
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_consumers.remote import (
    RemoteMessageConsumer,
    RemoteMessageConsumerDef,
)
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.message_queues.remote_client import RemoteClientMessageQueue

if TYPE_CHECKING:
    from urllib.parse import SplitResult


@pytest.fixture()
def message_queue() -> SimpleMessageQueue:
    return SimpleMessageQueue(host="mock-url.io", port=8001)


@pytest.fixture()
def side_effect(message_queue: SimpleMessageQueue) -> Callable:
    test_client = TestClient(message_queue._app)

    def side_effect(url: str, json: Dict) -> Dict[str, str]:
        split_result: SplitResult = urlsplit(url)
        return test_client.post(
            split_result.path,
            json=json,
        )

    return side_effect


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.mark.asyncio
@patch("agentfile.message_queues.remote_client.httpx.AsyncClient.post")
async def test_remote_client_register_consumer(
    mock_post: MagicMock, message_queue: SimpleMessageQueue, side_effect: Callable
) -> None:
    # Arrange
    _test_client = TestClient(message_queue._app)
    remote_mq = RemoteClientMessageQueue(base_url="https://mock-url.io")
    remote_consumer = RemoteMessageConsumer(
        message_type="mock_type", url="remote-consumer.io"
    )
    remote_consumer_def = RemoteMessageConsumerDef(**remote_consumer.model_dump())
    mock_post.side_effect = side_effect

    # act
    result = await remote_mq.register_consumer(consumer=remote_consumer)

    # assert
    mock_post.assert_called_once_with(
        "https://mock-url.io/register_consumer", json=remote_consumer_def.model_dump()
    )
    assert len(message_queue.consumers) == 1
    assert result.status_code == 200


@pytest.mark.asyncio
@patch("agentfile.message_queues.remote_client.httpx.AsyncClient.post")
async def test_remote_client_deregister_consumer(
    mock_post: MagicMock, message_queue: SimpleMessageQueue, side_effect: Callable
) -> None:
    # Arrange
    remote_mq = RemoteClientMessageQueue(base_url="https://mock-url.io")
    remote_consumer = RemoteMessageConsumer(
        message_type="mock_type", url="remote-consumer.io"
    )
    remote_consumer_def = RemoteMessageConsumerDef(**remote_consumer.model_dump())
    await message_queue.register_consumer(remote_consumer)
    mock_post.side_effect = side_effect

    # act
    result = await remote_mq.deregister_consumer(consumer=remote_consumer)

    # assert
    mock_post.assert_called_once_with(
        "https://mock-url.io/deregister_consumer", json=remote_consumer_def.model_dump()
    )
    assert len(message_queue.consumers) == 0
    assert result.status_code == 200
