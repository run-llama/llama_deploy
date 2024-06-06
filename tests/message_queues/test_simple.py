import asyncio
import pytest
from typing import Any, List
from llama_index.core.bridge.pydantic import PrivateAttr
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.messages.base import BaseMessage


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[BaseMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: BaseMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


class MockMessage(BaseMessage):
    @classmethod
    def class_name(cls) -> str:
        return "MockMessage"


@pytest.mark.asyncio()
async def test_simple_register_consumer() -> None:
    # Arrange
    consumer_one = MockMessageConsumer()
    consumer_two = MockMessageConsumer(message_type=MockMessage)
    mq = SimpleMessageQueue()

    # Act
    await mq.register_consumer(consumer_one)
    await mq.register_consumer(consumer_two)
    with pytest.raises(ValueError):
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
    consumer_two = MockMessageConsumer(message_type=MockMessage)
    consumer_three = MockMessageConsumer(message_type=MockMessage)
    mq = SimpleMessageQueue()

    await mq.register_consumer(consumer_one)
    await mq.register_consumer(consumer_two)
    await mq.register_consumer(consumer_three)

    # Act
    await mq.deregister_consumer(consumer_one)
    await mq.deregister_consumer(consumer_three)
    with pytest.raises(ValueError):
        await mq.deregister_consumer(consumer_three)

    # Assert
    assert len(await mq.get_consumers(MockMessage)) == 1
    assert len(await mq.get_consumers(BaseMessage)) == 0


@pytest.mark.asyncio()
async def test_simple_publish_consumer() -> None:
    # Arrange
    consumer_one = MockMessageConsumer()
    consumer_two = MockMessageConsumer(message_type=MockMessage)
    mq = SimpleMessageQueue()
    task = asyncio.create_task(mq.start())

    await mq.register_consumer(consumer_one)
    await mq.register_consumer(consumer_two)

    # Act
    await mq.publish(BaseMessage(id_="1"))
    await mq.publish(MockMessage(id_="2"))
    await mq.publish(MockMessage(id_="3"))

    # Give some time for last message to get published and sent to consumers
    await asyncio.sleep(0.5)
    task.cancel()

    # Assert
    assert ["1"] == [m.id_ for m in consumer_one.processed_messages]
    assert ["2", "3"] == [m.id_ for m in consumer_two.processed_messages]
