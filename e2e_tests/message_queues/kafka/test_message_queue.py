import asyncio

import pytest

from llama_deploy.client import Client
from llama_deploy.types import QueueMessage


@pytest.mark.asyncio
async def test_roundtrip(mq):
    # produce a message
    test_message = QueueMessage(type="test_message", data={"message": "this is a test"})
    await mq.publish(test_message, topic="test")

    await asyncio.sleep(0)

    async for m in mq.get_messages("test"):
        assert m == test_message
        break

    # Give time for shutting down kafka consumer
    await asyncio.sleep(1)


@pytest.mark.asyncio
async def test_multiple_control_planes(control_planes):
    c1 = Client(control_plane_url="http://localhost:8001")
    c2 = Client(control_plane_url="http://localhost:8002")

    session = await c1.core.sessions.create()
    r1 = await session.run("basic", arg="Hello One!")
    await c1.core.sessions.delete(session.id)
    assert r1 == "Workflow one received Hello One!"

    session = await c2.core.sessions.create()
    r2 = await session.run("basic", arg="Hello Two!")
    await c2.core.sessions.delete(session.id)
    assert r2 == "Workflow two received Hello Two!"
