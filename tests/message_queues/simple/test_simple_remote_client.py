import asyncio
from typing import TYPE_CHECKING, Any, Callable, Dict, List
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import PrivateAttr

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
    SimpleMessageQueueConfig,
    SimpleMessageQueueServer,
)
from llama_deploy.messages.base import QueueMessage
from llama_deploy.types import ActionTypes

if TYPE_CHECKING:
    from urllib.parse import SplitResult


@pytest.fixture()
def message_queue() -> SimpleMessageQueueServer:
    return SimpleMessageQueueServer(host="mock-url.io", port=8001)


@pytest.fixture()
def post_side_effect(message_queue: SimpleMessageQueueServer) -> Callable:
    test_client = TestClient(message_queue._app)

    def side_effect(url: str, json: Dict) -> httpx.Response:
        split_result: SplitResult = urlsplit(url)
        return test_client.post(
            split_result.path,
            json=json,
        )

    return side_effect


@pytest.fixture()
def get_side_effect(message_queue: SimpleMessageQueueServer) -> Callable:
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
@patch("llama_deploy.message_queues.simple.client.httpx.AsyncClient.post")
async def test_remote_client_register_consumer(
    mock_post: MagicMock,
    message_queue: SimpleMessageQueueServer,
    post_side_effect: Callable,
) -> None:
    # Arrange
    remote_mq = SimpleMessageQueue(
        SimpleMessageQueueConfig(
            host="mock-url.io",
            port=message_queue.port,
        )
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
        "http://mock-url.io:8001/register_consumer",
        json=remote_consumer_def.model_dump(),
    )
    assert len(message_queue.consumers) == 1
    assert result == default_start_consuming_callable


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.simple.client.httpx.AsyncClient.post")
async def test_remote_client_deregister_consumer(
    mock_post: MagicMock,
    message_queue: SimpleMessageQueueServer,
    post_side_effect: Callable,
) -> None:
    # Arrange
    remote_mq = SimpleMessageQueue(
        SimpleMessageQueueConfig(
            host="mock-url.io",
            port=message_queue.port,
        )
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
        "http://mock-url.io:8001/deregister_consumer",
        json=remote_consumer_def.model_dump(),
    )
    assert len(message_queue.consumers) == 0
    assert result.status_code == 200


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.simple.client.httpx.AsyncClient.get")
async def test_remote_client_get_consumers(
    mock_get: MagicMock,
    message_queue: SimpleMessageQueueServer,
    get_side_effect: Callable,
) -> None:
    # Arrange
    remote_mq = SimpleMessageQueue(
        SimpleMessageQueueConfig(
            host="mock-url.io",
            port=message_queue.port,
        )
    )
    remote_consumer = RemoteMessageConsumer(
        message_type="mock_type", url="remote-consumer.io"
    )
    await message_queue.register_consumer(remote_consumer)
    mock_get.side_effect = get_side_effect

    # act
    result = await remote_mq.get_consumers(message_type="mock_type")

    # assert
    mock_get.assert_called_once_with("http://mock-url.io:8001/get_consumers/mock_type")
    assert len(message_queue.consumers) == 1
    assert result[0] == remote_consumer


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.simple.client.httpx.AsyncClient.post")
async def test_remote_client_publish(
    mock_post: MagicMock,
    message_queue: SimpleMessageQueueServer,
    post_side_effect: Callable,
) -> None:
    # Arrange
    consumer = MockMessageConsumer(message_type="mock_type")
    await message_queue.register_consumer(consumer)
    remote_mq = SimpleMessageQueue(
        SimpleMessageQueueConfig(
            host=message_queue.host,
            port=message_queue.port,
        )
    )
    mock_post.side_effect = post_side_effect

    # act
    message = QueueMessage(
        type="mock_type", data={"payload": "mock payload"}, action=ActionTypes.NEW_TASK
    )
    await remote_mq.publish(message=message, topic="mock_type")

    # assert
    mock_post.assert_called_once_with(
        "http://mock-url.io:8001/publish/mock_type", json=message.model_dump()
    )
    assert message_queue.queues["mock_type"][0] == message


@pytest.mark.asyncio()
async def test_simple_register_consumer(message_queue_server) -> None:
    # Arrange
    consumer_one = MockMessageConsumer(type="one")
    consumer_two = MockMessageConsumer(type="two")
    mq = SimpleMessageQueue(SimpleMessageQueueConfig(raise_exceptions=True))

    # Act
    await mq.register_consumer(consumer_one)
    await mq.register_consumer(consumer_two)
    with pytest.raises(
        ValueError, match="A consumer with the same url has previously been registered"
    ):
        await mq.register_consumer(consumer_two)

    # Assert
    assert consumer_one.id_ in [c.id_ for c in await mq.get_consumers("topic_one")]
    assert consumer_two.id_ in [c.id_ for c in await mq.get_consumers("topic_two")]


@pytest.mark.asyncio()
async def test_simple_deregister_consumer(message_queue_server) -> None:
    # Arrange
    consumer_one = MockMessageConsumer()
    consumer_two = MockMessageConsumer(message_type="one")
    consumer_three = MockMessageConsumer(message_type="two")
    mq = SimpleMessageQueue(SimpleMessageQueueConfig(raise_exceptions=True))

    await mq.register_consumer(consumer_one, topic="topic_one")
    await mq.register_consumer(consumer_two, topic="topic_two")
    await mq.register_consumer(consumer_three, topic="topic_three")

    # Act
    await mq.deregister_consumer(consumer_one)
    await mq.deregister_consumer(consumer_three)
    with pytest.raises(ValueError, match="No consumer found"):
        await mq.deregister_consumer(consumer_three)

    # Assert
    assert len(await mq.get_consumers("topic_two")) == 1
    assert len(await mq.get_consumers("topic_three")) == 0
