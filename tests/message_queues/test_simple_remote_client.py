import asyncio
from typing import Any, Callable, Dict, List, TYPE_CHECKING
from unittest.mock import patch, MagicMock
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import PrivateAttr

from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    default_start_consuming_callable,
)
from llama_deploy.message_consumers.remote import (
    RemoteMessageConsumer,
    RemoteMessageConsumerDef,
)
from llama_deploy.message_queues.simple import (
    SimpleMessageQueue,
    SimpleRemoteClientMessageQueue,
)
from llama_deploy.types import ActionTypes

if TYPE_CHECKING:
    from urllib.parse import SplitResult


@pytest.fixture()
def message_queue() -> SimpleMessageQueue:
    return SimpleMessageQueue(host="https://mock-url.io", port=8001)


@pytest.fixture()
def post_side_effect(message_queue: SimpleMessageQueue) -> Callable:
    test_client = TestClient(message_queue._app)

    def side_effect(url: str, json: Dict) -> httpx.Response:
        split_result: SplitResult = urlsplit(url)
        return test_client.post(
            split_result.path,
            json=json,
        )

    return side_effect


@pytest.fixture()
def get_side_effect(message_queue: SimpleMessageQueue) -> Callable:
    test_client = TestClient(message_queue._app)

    def side_effect(url: str) -> Any:
        return test_client.get(url)

    return side_effect


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.simple.httpx.AsyncClient.post")
async def test_remote_client_register_consumer(
    mock_post: MagicMock, message_queue: SimpleMessageQueue, post_side_effect: Callable
) -> None:
    # Arrange
    remote_mq = SimpleRemoteClientMessageQueue(
        base_url="https://mock-url.io", host=message_queue.host, port=message_queue.port
    )
    remote_consumer = RemoteMessageConsumer(
        message_type="mock_type", url="remote-consumer.io"
    )
    remote_consumer_def = RemoteMessageConsumerDef(**remote_consumer.model_dump())
    mock_post.side_effect = post_side_effect

    # act
    result = await remote_mq.register_consumer(consumer=remote_consumer)

    # assert
    mock_post.assert_called_once_with(
        "https://mock-url.io/register_consumer", json=remote_consumer_def.model_dump()
    )
    assert len(message_queue.consumers) == 1
    assert result == default_start_consuming_callable


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.simple.httpx.AsyncClient.post")
async def test_remote_client_deregister_consumer(
    mock_post: MagicMock, message_queue: SimpleMessageQueue, post_side_effect: Callable
) -> None:
    # Arrange
    remote_mq = SimpleRemoteClientMessageQueue(
        base_url="https://mock-url.io", host=message_queue.host, port=message_queue.port
    )
    remote_consumer = RemoteMessageConsumer(
        message_type="mock_type", url="remote-consumer.io"
    )
    remote_consumer_def = RemoteMessageConsumerDef(**remote_consumer.model_dump())
    await message_queue.register_consumer(remote_consumer)
    mock_post.side_effect = post_side_effect

    # act
    result = await remote_mq.deregister_consumer(consumer=remote_consumer)

    # assert
    mock_post.assert_called_once_with(
        "https://mock-url.io/deregister_consumer", json=remote_consumer_def.model_dump()
    )
    assert len(message_queue.consumers) == 0
    assert result.status_code == 200


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.simple.httpx.AsyncClient.get")
async def test_remote_client_get_consumers(
    mock_get: MagicMock, message_queue: SimpleMessageQueue, get_side_effect: Callable
) -> None:
    # Arrange
    remote_mq = SimpleRemoteClientMessageQueue(
        base_url="https://mock-url.io", host=message_queue.host, port=message_queue.port
    )
    remote_consumer = RemoteMessageConsumer(
        message_type="mock_type", url="remote-consumer.io"
    )
    await message_queue.register_consumer(remote_consumer)
    mock_get.side_effect = get_side_effect

    # act
    result = await remote_mq.get_consumers(message_type="mock_type")

    # assert
    mock_get.assert_called_once_with("https://mock-url.io/get_consumers/mock_type")
    assert len(message_queue.consumers) == 1
    assert result[0] == remote_consumer


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.simple.httpx.AsyncClient.post")
async def test_remote_client_publish(
    mock_post: MagicMock, message_queue: SimpleMessageQueue, post_side_effect: Callable
) -> None:
    # Arrange
    consumer = MockMessageConsumer(message_type="mock_type")
    await message_queue.register_consumer(consumer)
    remote_mq = SimpleRemoteClientMessageQueue(
        base_url=message_queue.host, host=message_queue.host, port=message_queue.port
    )
    mock_post.side_effect = post_side_effect

    # act
    message = QueueMessage(
        type="mock_type", data={"payload": "mock payload"}, action=ActionTypes.NEW_TASK
    )
    await remote_mq.publish(message=message)

    # assert
    mock_post.assert_called_once_with(
        "https://mock-url.io/publish", json=message.model_dump()
    )
    assert message_queue.queues["mock_type"][0] == message
