from abc import ABC, abstractmethod
from typing import Any

from llama_index.core.bridge.pydantic import BaseModel

from agentfile.messages.base import QueueMessage
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_publishers.publisher import MessageQueuePublisherMixin
from agentfile.types import ServiceDefinition


class BaseService(MessageQueuePublisherMixin, ABC, BaseModel):
    """Base class for a service."""

    service_name: str

    class Config:
        arbitrary_types_allowed = True

    @property
    @abstractmethod
    def service_definition(self) -> ServiceDefinition:
        """The service definition."""
        ...

    @abstractmethod
    def as_consumer(self) -> BaseMessageQueueConsumer:
        """Get the consumer for the message queue."""
        ...

    @abstractmethod
    async def processing_loop(self) -> None:
        """The processing loop for the service."""
        ...

    @abstractmethod
    async def process_message(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Process a message."""
        ...

    async def publish(self, message: QueueMessage, **kwargs: Any) -> None:
        """Publish a message to another service."""
        message.publisher_id = self.publisher_id
        await self.message_queue.publish(
            message, callback=self.publish_callback, **kwargs
        )

    @abstractmethod
    async def launch_local(self) -> None:
        """Launch the service in-process."""
        ...

    @abstractmethod
    async def launch_server(self) -> None:
        """Launch the service as a server."""
        ...
