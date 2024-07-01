from abc import ABC, abstractmethod
from typing import Any, Optional
from llama_agents.messages.base import QueueMessage
from llama_agents.message_queues.base import BaseMessageQueue, PublishCallback


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

    async def publish(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Publish message."""
        message.publisher_id = self.publisher_id
        return await self.message_queue.publish(
            message, callback=self.publish_callback, **kwargs
        )
