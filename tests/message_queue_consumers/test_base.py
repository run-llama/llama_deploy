import asyncio
import pytest
from pydantic import PrivateAttr
from typing import Any, List

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.simple import SimpleMessageQueue
from llama_deploy.messages.base import QueueMessage


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.mark.asyncio()
async def test_consumer_consumes_messages() -> None:
    # Arrange
    consumer_one = MockMessageConsumer()
    mq = SimpleMessageQueue()
    task = await mq.launch_local()

    # Act
    start_consuming_callable = await mq.register_consumer(consumer_one)
    await start_consuming_callable()
    await asyncio.sleep(0.1)
    await mq.publish(QueueMessage(publisher_id="test", id_="1"))
    await mq.publish(QueueMessage(publisher_id="test", id_="2"))

    # Give some time for last message to get published and sent to consumers
    await asyncio.sleep(0.5)
    task.cancel()

    # Assert
    assert consumer_one.id_ in [
        c.id_ for c in await mq.get_consumers(consumer_one.message_type)
    ]
    assert ["1", "2"] == [m.id_ for m in consumer_one.processed_messages]
