import pytest
from typing import Any
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.messages.base import BaseMessage


class MockMessageConsumer(BaseMessageQueueConsumer):
    async def _process_message(self, message: BaseMessage, **kwargs: Any) -> Any:
        print(f"Processed: {message.class_name()}")


@pytest.mark.asyncio()
async def test_simple_register_consumer() -> None:
    # Arrange
    consumer = MockMessageConsumer()
    mq = SimpleMessageQueue()

    # Act
    await mq.register_consumer(consumer)

    # Assert
    assert consumer.id_ in [
        c.id_ for c in await mq.get_consumers(consumer.message_type)
    ]
