import pytest

from llama_deploy.message_queues.simple.client import SimpleMessageQueue
from llama_deploy.message_queues.simple.config import SimpleMessageQueueConfig


@pytest.mark.asyncio
async def test_cleanup_local() -> None:
    mq = SimpleMessageQueue()
    await mq.cleanup()


def test_as_config() -> None:
    cfg = SimpleMessageQueueConfig()
    mq = SimpleMessageQueue(cfg)
    assert mq.as_config() == cfg
