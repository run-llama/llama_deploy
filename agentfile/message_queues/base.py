"""Message queue module."""

from abc import ABC, abstractmethod
from typing import Any, Protocol
from llama_index.core.bridge.pydantic import BaseModel
from agentfile.messages.base import BaseMessage
from agentfile.message_consumers.base import BaseMessageQueueConsumer


class MessageProcessor(Protocol):
    """Protocol for a callable that processes messages."""

    def __call__(self, message: BaseMessage, **kwargs: Any) -> None:
        ...


class BaseMessageQueue(BaseModel, ABC):
    """Message broker interface between publisher and consumer."""

    @abstractmethod
    async def _publish(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Subclasses implement publish logic here."""
        ...

    async def publish(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Send message to a consumer."""
        await self._publish(message, **kwargs)

    @abstractmethod
    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, **kwargs: Any
    ) -> Any:
        """Register consumer to start consuming messages."""

    @abstractmethod
    async def deregister_consumer(self, consumer_id: str, message_type_str: str) -> Any:
        """Deregister consumer to stop publishing messages)."""
