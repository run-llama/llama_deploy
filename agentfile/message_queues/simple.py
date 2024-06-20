"""Simple Message Queue."""

import asyncio
import random
import logging

from collections import deque
from typing import Any, Dict, List
from llama_index.core.bridge.pydantic import Field
from agentfile.message_queues.base import BaseMessageQueue
from agentfile.messages.base import QueueMessage
from agentfile.message_consumers.base import BaseMessageQueueConsumer

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class SimpleMessageQueue(BaseMessageQueue):
    """SimpleMessageQueue.

    An in-memory message queue that implements a push model for consumers.
    """

    consumers: Dict[str, Dict[str, BaseMessageQueueConsumer]] = Field(
        default_factory=dict
    )
    queues: Dict[str, deque] = Field(default_factory=dict)
    running: bool = True

    def __init__(
        self,
        consumers: Dict[str, Dict[str, BaseMessageQueueConsumer]] = {},
        queues: Dict[str, deque] = {},
    ):
        super().__init__(consumers=consumers, queues=queues)

    def _select_consumer(self, message: QueueMessage) -> BaseMessageQueueConsumer:
        """Select a single consumer to publish a message to."""
        message_type_str = message.type
        consumer_id = random.choice(list(self.consumers[message_type_str].keys()))
        return self.consumers[message_type_str][consumer_id]

    async def _publish(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Publish message to a queue."""
        message_type_str = message.type

        if message_type_str not in self.consumers:
            logger.debug(
                f"Failed to publish message. No registered consumer '{message_type_str}'."
            )
            raise ValueError(
                f"No consumer for '{message_type_str}' has been registered."
            )

        if message_type_str not in self.queues:
            self.queues[message_type_str] = deque()

        self.queues[message_type_str].append(message)

    async def _publish_to_consumer(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Publish message to a consumer."""
        consumer = self._select_consumer(message)
        try:
            await consumer.process_message(message, **kwargs)
        except Exception:
            raise

    async def start(self) -> None:
        """A loop for getting messages from queues and sending to consumer."""
        while self.running:
            for queue in self.queues.values():
                if queue:
                    message: QueueMessage = queue.popleft()
                    message.stats.process_start_time = message.stats.timestamp_str()
                    await self._publish_to_consumer(message)
                    message.stats.process_end_time = (
                        message.stats.timestamp_str()
                    )  # TODO dedicated ack
            await asyncio.sleep(0.1)

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, **kwargs: Any
    ) -> None:
        """Register a new consumer."""
        message_type_str = consumer.message_type

        if message_type_str not in self.consumers:
            self.consumers[message_type_str] = {consumer.id_: consumer}
        else:
            if consumer.id_ in self.consumers[message_type_str]:
                raise ValueError("Consumer has already been added.")

            self.consumers[message_type_str][consumer.id_] = consumer

        if message_type_str not in self.queues:
            self.queues[message_type_str] = deque()

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> None:
        message_type_str = consumer.message_type
        if consumer.id_ not in self.consumers.get(message_type_str, {}):
            raise ValueError("No consumer found for associated message type.")

        del self.consumers[message_type_str][consumer.id_]
        if len(self.consumers[message_type_str]) == 0:
            del self.consumers[message_type_str]

    async def get_consumers(self, message_type: str) -> List[BaseMessageQueueConsumer]:
        if message_type not in self.consumers:
            return []

        return list(self.consumers[message_type].values())
