import asyncio
import pytest
from fastapi import HTTPException
from pydantic import PrivateAttr
from typing import Any, List

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.simple import SimpleMessageQueue
from llama_deploy.messages.base import QueueMessage


class MockMessageConsumer(BaseMessageQueueConsumer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.mark.asyncio()
async def test_simple_register_consumer() -> None:
    # Arrange
    consumer_one = MockMessageConsumer()
    consumer_two = MockMessageConsumer(type="two")
    mq = SimpleMessageQueue()

    # Act
    await mq.register_consumer(consumer_one)
    await mq.register_consumer(consumer_two)
    with pytest.raises(HTTPException):
        await mq.register_consumer(consumer_two)

    # Assert
    assert consumer_one.id_ in [
        c.id_ for c in await mq.get_consumers(consumer_one.message_type)
    ]
    assert consumer_two.id_ in [
        c.id_ for c in await mq.get_consumers(consumer_two.message_type)
    ]


@pytest.mark.asyncio()
async def test_simple_deregister_consumer() -> None:
    # Arrange
    consumer_one = MockMessageConsumer()
    consumer_two = MockMessageConsumer(message_type="one")
    consumer_three = MockMessageConsumer(message_type="two")
    mq = SimpleMessageQueue()

    await mq.register_consumer(consumer_one)
    await mq.register_consumer(consumer_two)
    await mq.register_consumer(consumer_three)

    # Act
    await mq.deregister_consumer(consumer_one)
    await mq.deregister_consumer(consumer_three)
    with pytest.raises(HTTPException):
        await mq.deregister_consumer(consumer_three)

    # Assert
    assert len(await mq.get_consumers("one")) == 1
    assert len(await mq.get_consumers("zero")) == 0


@pytest.mark.asyncio()
async def test_simple_publish_consumer() -> None:
    # Arrange
    consumer_one = MockMessageConsumer()
    consumer_two = MockMessageConsumer(message_type="two")
    mq = SimpleMessageQueue()
    task = await mq.launch_local()

    await mq.register_consumer(consumer_one)
    await mq.register_consumer(consumer_two)

    # Act
    await mq.publish(QueueMessage(publisher_id="test", id_="1"))
    await mq.publish(QueueMessage(publisher_id="test", id_="2", type="two"))
    await mq.publish(QueueMessage(publisher_id="test", id_="3", type="two"))

    # Give some time for last message to get published and sent to consumers
    await asyncio.sleep(0.5)
    task.cancel()

    # Assert
    assert ["1"] == [m.id_ for m in consumer_one.processed_messages]
    assert ["2", "3"] == [m.id_ for m in consumer_two.processed_messages]
