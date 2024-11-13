import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.redis import RedisMessageQueue
from llama_deploy.messages.base import QueueMessage


class MockPubSub:
    async def subscribe(self, channel: str) -> None:
        pass

    async def get_message(self, ignore_subscribe_messages: bool = True) -> None:
        return None

    async def unsubscribe(self, channel: str) -> None:
        pass


class MockRedisConnection:
    async def publish(self, channel: str, message: str) -> int:
        return 1

    def pubsub(self) -> MockPubSub:
        return MockPubSub()


class MockConsumer(BaseMessageQueueConsumer):
    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> Any:
        pass


@pytest.fixture
def redis_queue() -> RedisMessageQueue:
    return RedisMessageQueue(url="redis://localhost:6379")


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.redis._establish_connection")
async def test_new_connection(
    mock_establish_connection: AsyncMock, redis_queue: RedisMessageQueue
) -> None:
    mock_establish_connection.return_value = MockRedisConnection()

    connection = await redis_queue.new_connection()

    assert isinstance(connection, MockRedisConnection)
    mock_establish_connection.assert_called_once_with("redis://localhost:6379")


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.redis._establish_connection")
async def test_publish(
    mock_establish_connection: AsyncMock, redis_queue: RedisMessageQueue
) -> None:
    mock_redis = AsyncMock()
    mock_establish_connection.return_value = mock_redis

    test_message = QueueMessage(type="test_channel", data={"key": "value"})
    expected_json = json.dumps(test_message.model_dump())

    await redis_queue._publish(test_message, topic="test_channel")

    mock_establish_connection.assert_called_once_with("redis://localhost:6379")
    mock_redis.publish.assert_called_once_with(test_message.type, expected_json)


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.redis._establish_connection")
async def test_register_consumer(
    mock_establish_connection: AsyncMock, redis_queue: RedisMessageQueue
) -> None:
    mock_redis = MockRedisConnection()
    mock_establish_connection.return_value = mock_redis

    consumer = MockConsumer(message_type="test_channel")
    start_consuming = await redis_queue.register_consumer(consumer)

    assert callable(start_consuming)
    assert consumer.id_ in redis_queue._consumers


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.redis._establish_connection")
async def test_deregister_consumer(
    mock_establish_connection: AsyncMock, redis_queue: RedisMessageQueue
) -> None:
    mock_redis = MockRedisConnection()
    mock_establish_connection.return_value = mock_redis

    consumer = MockConsumer(message_type="test_channel")
    await redis_queue.register_consumer(consumer)
    await redis_queue.deregister_consumer(consumer)

    assert consumer.id_ not in redis_queue._consumers


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.redis._establish_connection")
async def test_cleanup_local(
    mock_establish_connection: AsyncMock, redis_queue: RedisMessageQueue
) -> None:
    mock_redis = AsyncMock()
    mock_establish_connection.return_value = mock_redis

    await redis_queue.new_connection()
    await redis_queue.cleanup_local([])

    mock_redis.close.assert_called_once()
    assert redis_queue._redis is None
    assert redis_queue._consumers == {}


@pytest.mark.asyncio
async def test_from_url_params() -> None:
    queue = RedisMessageQueue.from_url_params(
        host="localhost", port=6379, db=0, username="user", password="pass", ssl=True
    )
    assert queue.url == "rediss://user:pass@localhost:6379/0"

    queue = RedisMessageQueue.from_url_params(host="localhost", port=6379, db=0)
    assert queue.url == "redis://localhost:6379/0"


@pytest.mark.asyncio
@patch("llama_deploy.message_queues.redis._establish_connection")
async def test_register_same_consumer_twice(
    mock_establish_connection: AsyncMock, redis_queue: RedisMessageQueue
) -> None:
    mock_redis = MockRedisConnection()
    mock_establish_connection.return_value = mock_redis

    consumer = MockConsumer(message_type="test_channel")

    start_consuming_1 = await redis_queue.register_consumer(consumer)
    start_consuming_2 = await redis_queue.register_consumer(consumer)

    assert callable(start_consuming_1)
    assert callable(start_consuming_2)
    assert start_consuming_1 == start_consuming_2
    assert len(redis_queue._consumers) == 1
