import asyncio
import httpx
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Any

from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.message_publishers.publisher import MessageQueuePublisherMixin
from llama_agents.types import ServiceDefinition


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
    def as_consumer(self, remote: bool = False) -> BaseMessageQueueConsumer:
        """Get the consumer for the message queue."""
        ...

    @abstractmethod
    async def processing_loop(self) -> None:
        """The processing loop for the service."""
        ...

    @abstractmethod
    async def process_message(self, message: QueueMessage) -> Any:
        """Process a message."""
        ...

    async def publish(self, message: QueueMessage, **kwargs: Any) -> None:
        """Publish a message to another service."""
        message.publisher_id = self.publisher_id
        await self.message_queue.publish(
            message, callback=self.publish_callback, **kwargs
        )

    @abstractmethod
    async def launch_local(self) -> asyncio.Task:
        """Launch the service in-process."""
        ...

    @abstractmethod
    async def launch_server(self) -> None:
        """Launch the service as a server."""
        ...

    async def register_to_control_plane(self, control_plane_url: str) -> None:
        """Register the service to the control plane."""
        service_def = self.service_definition
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{control_plane_url}/services/register",
                json=service_def.model_dump(),
            )
            response.raise_for_status()

    async def register_to_message_queue(self) -> None:
        """Register the service to the message queue."""
        await self.message_queue.register_consumer(self.as_consumer(remote=True))
