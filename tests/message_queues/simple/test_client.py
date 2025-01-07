import pytest

from llama_deploy.message_queues.simple.client import SimpleMessageQueue
from llama_deploy.message_queues.simple.config import SimpleMessageQueueConfig
from llama_deploy.message_queues.simple.server import SimpleMessageQueueServer

from .conftest import MockMessageConsumer


@pytest.mark.asyncio
async def test_register_consumer(
    message_queue_server: SimpleMessageQueueServer,
) -> None:
    mq = SimpleMessageQueue()
    consumer = MockMessageConsumer()
    await mq.register_consumer(consumer, topic="test_topic")
    with pytest.raises(ValueError, match="already registered for topic"):
        await mq.register_consumer(consumer, topic="test_topic")
    assert len(mq._consumers["test_topic"]) == 1

    await mq.deregister_consumer(consumer)
    assert len(mq._consumers["test_topic"]) == 0


@pytest.mark.asyncio
async def test_cleanup_local() -> None:
    mq = SimpleMessageQueue()
    await mq.cleanup()


def test_as_config() -> None:
    cfg = SimpleMessageQueueConfig()
    mq = SimpleMessageQueue(cfg)
    assert mq.as_config() == cfg
