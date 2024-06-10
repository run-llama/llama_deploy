from abc import ABC, abstractmethod
from typing import Any
from agentfile.messages.base import QueueMessage
from agentfile.message_queues.base import BaseMessageQueue


class MessageQueuePublisherMixin(ABC):
    """PublisherMixing."""

    @property
    @abstractmethod
    def publisher_id(self) -> str:
        ...

    @property
    @abstractmethod
    def message_queue(self) -> BaseMessageQueue:
        ...

    async def publish(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Publish message."""
        return await self.message_queue.publish(message, **kwargs)
