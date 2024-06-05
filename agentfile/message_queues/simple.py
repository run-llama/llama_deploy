"""Simple Message Queue."""

import random

from queue import Queue
from typing import Any, Dict, List, Type
from llama_index.core.bridge.pydantic import Field
from agentfile.message_queues.base import BaseMessageQueue
from agentfile.messages.base import BaseMessage
from agentfile.message_consumers.base import BaseMessageQueueConsumer


class SimpleMessageQueue(BaseMessageQueue):
    """SimpleMessageQueue.

    An in-memory message queue that implements a push model for consumers.
    """

    consumers: Dict[str, Dict[str, BaseMessageQueueConsumer]] = Field(
        default_factory=dict
    )
    queues: Dict[str, Queue] = Field(default_factory=dict)

    def _select_consumer(self, message: BaseMessage) -> BaseMessageQueueConsumer:
        """Select a single consumer to publish a message to."""
        message_type_str = message.class_name()
        consumer_id = random.choice(list(self.consumers[message_type_str].keys()))
        return self.consumers[message_type_str][consumer_id]

    async def _publish(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Publish message to a consumer."""

        consumer = self._select_consumer(message)
        try:
            await consumer.process_message(message, **kwargs)
        except Exception:
            raise

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, **kwargs: Any
    ) -> None:
        """Register a new consumer."""
        message_type_str = consumer.message_type.class_name()

        if message_type_str not in self.consumers:
            self.consumers[message_type_str] = {consumer.id_: consumer}
        else:
            if consumer.id_ in self.consumers[message_type_str]:
                raise ValueError("Consumer has already been added.")

            self.consumers[message_type_str][consumer.id_] = consumer

    async def deregister_consumer(
        self, consumer_id: str, message_type_str: str
    ) -> None:
        if consumer_id not in self.consumers[message_type_str]:
            raise ValueError("No consumer found for the supplied message type.")

        del self.consumers[message_type_str][consumer_id]

    async def get_consumers(
        self, message_type: Type[BaseMessage]
    ) -> List[BaseMessageQueueConsumer]:
        message_type_str = message_type.class_name()
        if message_type_str not in self.consumers:
            return []

        return list(self.consumers[message_type_str].values())
