import asyncio

import pytest

from llama_deploy import SimpleMessageQueue


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cancel_launch_server():
    mq = SimpleMessageQueue()
    t = asyncio.create_task(mq.launch_server())

    # Make sure the queue starts
    await asyncio.sleep(1)

    # Cancel
    t.cancel()
    await t
