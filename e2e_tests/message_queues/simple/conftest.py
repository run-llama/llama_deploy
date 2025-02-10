import asyncio

import pytest
import pytest_asyncio

from llama_deploy import (
    SimpleMessageQueue,
    SimpleMessageQueueConfig,
    SimpleMessageQueueServer,
)


@pytest_asyncio.fixture()
async def simple_server():
    queue = SimpleMessageQueueServer(SimpleMessageQueueConfig(port=8009))
    t = asyncio.create_task(queue.launch_server())
    # let message queue boot up
    await asyncio.sleep(1)

    yield

    t.cancel()
    await t


@pytest.fixture
def mq(simple_server):
    return SimpleMessageQueue(SimpleMessageQueueConfig(port=8009))
