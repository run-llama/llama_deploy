import asyncio

import pytest

from llama_deploy import Client
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_queues.redis import RedisMessageQueue
from llama_deploy.messages import QueueMessage


@pytest.mark.asyncio
async def test_roundtrip(mq: RedisMessageQueue):
    received_messages = []

    # register a consumer
    def message_handler(message: QueueMessage) -> None:
        received_messages.append(message)

    test_consumer = CallableMessageConsumer(
        message_type="test_message", handler=message_handler
    )
    start_consuming_callable = await mq.register_consumer(test_consumer, topic="test")
    t = asyncio.create_task(start_consuming_callable())
    await asyncio.sleep(1.0)

    # produce a message
    test_message = QueueMessage(type="test_message", data={"message": "this is a test"})
    await mq.publish(test_message, topic="test")
    await asyncio.sleep(1.0)
    t.cancel()
    await t

    # at this point message should've been arrived
    await mq.deregister_consumer(test_consumer)

    assert len(received_messages) == 1
    assert test_message in received_messages


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
