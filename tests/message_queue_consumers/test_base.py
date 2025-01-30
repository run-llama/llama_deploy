import asyncio
from typing import Any, List

import pytest
from pydantic import PrivateAttr

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.simple import (
    SimpleMessageQueue,
    SimpleMessageQueueServer,
)
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
    mq = SimpleMessageQueue()
    consumer_one = MockMessageConsumer()
    mqs = SimpleMessageQueueServer()
    server_task = asyncio.create_task(mqs.launch_server())
    await asyncio.sleep(0.5)

    # Act
    consuming_callable = await mq.register_consumer(consumer_one, topic="test")
    consuming_callable_task = asyncio.create_task(consuming_callable())

    await mq.publish(QueueMessage(publisher_id="test", id_="1"), topic="test")
    await mq.publish(QueueMessage(publisher_id="test", id_="2"), topic="test")
    # Give some time for last message to get published and sent to consumers
    await asyncio.sleep(0.5)

    # Assert
    assert consumer_one.id_ in mq._consumers["test"]
    assert ["1", "2"] == [m.id_ for m in consumer_one.processed_messages]

    # Tear down
    consuming_callable_task.cancel()
    server_task.cancel()
    await asyncio.gather(consuming_callable_task, server_task)
