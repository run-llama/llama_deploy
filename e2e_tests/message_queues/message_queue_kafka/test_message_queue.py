import asyncio

import pytest

from llama_deploy import Client
from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.messages import QueueMessage


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_roundtrip(mq):
    received_messages = []

    # register a consumer
    def message_handler(message: QueueMessage) -> None:
        received_messages.append(message)

    test_consumer = CallableMessageConsumer(
        message_type="test_message", handler=message_handler
    )
    start_consuming_callable = await mq.register_consumer(test_consumer, topic="test")

    # produce a message
    test_message = QueueMessage(type="test_message", data={"message": "this is a test"})

    # await asyncio.gather(start_consuming_callable(), mq.publish(test_message))
    await mq.publish(test_message, topic="test")
    t = asyncio.create_task(start_consuming_callable())
    await asyncio.sleep(0.5)
    # at this point message should've been arrived
    await mq.deregister_consumer(test_consumer)
    await t

    assert len(received_messages) == 1
    assert test_message in received_messages


@pytest.mark.e2e
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
