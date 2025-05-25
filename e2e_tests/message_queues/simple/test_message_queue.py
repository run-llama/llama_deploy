import asyncio

import pytest

from llama_deploy import (
    SimpleMessageQueue,
)
from llama_deploy.messages import QueueMessage


@pytest.mark.asyncio
async def test_roundtrip(mq: SimpleMessageQueue):
    # produce a message
    test_message = QueueMessage(type="test_message", data={"message": "this is a test"})
    await mq.publish(test_message, topic="test")

    await asyncio.sleep(0)

    async for m in mq.get_message("test"):
        assert m == test_message
        break
