from abc import ABC, abstractmethod
from typing import Any, Optional
from agentfile.messages.base import QueueMessage
from agentfile.message_queues.base import BaseMessageQueue, PublishCallback


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

    @property
    def publish_callback(self) -> Optional[PublishCallback]:
        return None

    async def publish(
        self, message: QueueMessage, callback: Optional[PublishCallback], **kwargs: Any
    ) -> Any:
        """Publish message."""
        return await self.message_queue.publish(message, callback=callback, **kwargs)
