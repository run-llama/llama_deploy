import asyncio
import os

import pytest

from llama_deploy import Client
from llama_deploy.messages import QueueMessage

pytestmark = pytest.mark.skipif(
    not os.environ.get("AWS_SECRET_ACCESS_KEY"), reason="AWS_SECRET_ACCESS_KEY not set"
)


@pytest.mark.asyncio
async def test_roundtrip(mq, topic_prefix):
    test_message = QueueMessage(type="test_message", data={"message": "this is a test"})
    await mq.publish(test_message, topic="test")

    await asyncio.sleep(0)

    async for m in mq.get_messages("test"):
        assert m.data == test_message.data
        break


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
