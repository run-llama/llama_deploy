import pytest

from llama_deploy.message_queues.simple.client import SimpleMessageQueue
from llama_deploy.message_queues.simple.config import SimpleMessageQueueConfig

from .conftest import MockMessageConsumer


@pytest.mark.asyncio
async def test_register_consumer(message_queue_server):
    mq = SimpleMessageQueue()
    consumer = MockMessageConsumer()
    await mq.register_consumer(consumer, topic="test_topic")
    with pytest.raises(ValueError, match="already registered for topic"):
        await mq.register_consumer(consumer, topic="test_topic")
    assert len(mq._consumers["test_topic"]) == 1

    await mq.deregister_consumer(consumer)
    assert len(mq._consumers["test_topic"]) == 0


@pytest.mark.asyncio
async def test_cleanup_local():
    mq = SimpleMessageQueue()
    with pytest.raises(NotImplementedError):
        await mq.cleanup_local([])


def test_as_config():
    cfg = SimpleMessageQueueConfig()
    mq = SimpleMessageQueue(cfg)
    assert mq.as_config() == cfg
