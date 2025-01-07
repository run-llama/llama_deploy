import json
import sys
from typing import Any, cast
from unittest import mock

import pytest

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.redis import RedisMessageQueue, RedisMessageQueueConfig
from llama_deploy.messages.base import QueueMessage


class MockConsumer(BaseMessageQueueConsumer):
    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> Any:
        pass


@pytest.fixture
def redis_queue(monkeypatch: Any) -> RedisMessageQueue:
    monkeypatch.setitem(sys.modules, "redis.asyncio", mock.MagicMock())
    rmq = RedisMessageQueue()
    rmq._redis = mock.AsyncMock(pubsub=mock.MagicMock(return_value=mock.AsyncMock()))
    return rmq


@pytest.mark.asyncio
async def test_publish(redis_queue: RedisMessageQueue) -> None:
    test_message = QueueMessage(type="test_channel", data={"key": "value"})
    expected_json = json.dumps(test_message.model_dump())

    await redis_queue._publish(test_message, topic="test_channel")

    redis_queue._redis.publish.assert_called_once_with(test_message.type, expected_json)  # type:ignore


@pytest.mark.asyncio
async def test_register_consumer(redis_queue: RedisMessageQueue) -> None:
    consumer = MockConsumer(message_type="test_channel")
    start_consuming = await redis_queue.register_consumer(consumer, "topic")

    assert callable(start_consuming)
    assert consumer.id_ in redis_queue._consumers


@pytest.mark.asyncio
async def test_deregister_consumer(redis_queue: RedisMessageQueue) -> None:
    consumer = MockConsumer(message_type="test_channel")
    await redis_queue.register_consumer(consumer, "topic")
    await redis_queue.deregister_consumer(consumer)

    assert consumer.id_ not in redis_queue._consumers


@pytest.mark.asyncio
async def test_cleanup(redis_queue: RedisMessageQueue) -> None:
    await redis_queue.cleanup()

    redis_queue._redis.aclose.assert_called_once()  # type:ignore
    assert redis_queue._consumers == {}


@pytest.mark.asyncio
async def test_register_same_consumer_twice(redis_queue: RedisMessageQueue) -> None:
    consumer = MockConsumer(message_type="test_channel")

    start_consuming_1 = await redis_queue.register_consumer(consumer, "topic")
    start_consuming_2 = await redis_queue.register_consumer(consumer, "topic")

    assert callable(start_consuming_1)
    assert callable(start_consuming_2)
    assert start_consuming_1 == start_consuming_2
    assert len(redis_queue._consumers) == 1


def test_config() -> None:
    cfg = RedisMessageQueueConfig(host="localhost", port=1515)
    assert cfg.url == "redis://localhost:1515/"


def test_missing_deps(monkeypatch: Any) -> None:
    # Mock the import mechanism to raise ImportError for redis
    def mock_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name.startswith("redis"):
            raise ImportError(f"No module named '{name}'")
        return original_import(name, *args, **kwargs)

    # Store the original import
    original_import = __import__
    # Replace the import mechanism with our mock
    monkeypatch.setattr("builtins.__import__", mock_import)

    with pytest.raises(ValueError, match="Missing redis optional dependency"):
        RedisMessageQueue()


def test_as_config(redis_queue: RedisMessageQueue) -> None:
    default_config = RedisMessageQueueConfig()
    res = cast(RedisMessageQueueConfig, redis_queue.as_config())
    assert res.url == default_config.url
