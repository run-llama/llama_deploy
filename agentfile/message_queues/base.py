"""Message queue module."""

import inspect
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Protocol, TYPE_CHECKING
from llama_index.core.bridge.pydantic import BaseModel
from agentfile.messages.base import QueueMessage

if TYPE_CHECKING:
    from agentfile.message_consumers.base import BaseMessageQueueConsumer

import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(level=logging.INFO)


class MessageProcessor(Protocol):
    """Protocol for a callable that processes messages."""

    def __call__(self, message: QueueMessage, **kwargs: Any) -> None:
        ...


class PublishCallback(Protocol):
    """Protocol for a callable that processes messages."""

    def __call__(self, message: QueueMessage, **kwargs: Any) -> None:
        ...


class BaseMessageQueue(BaseModel, ABC):
    """Message broker interface between publisher and consumer."""

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def _publish(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Subclasses implement publish logic here."""
        ...

    async def publish(
        self,
        message: QueueMessage,
        callback: Optional[PublishCallback] = None,
        **kwargs: Any
    ) -> Any:
        """Send message to a consumer."""
        logger.info("Publishing message: " + str(message))
        await self._publish(message, **kwargs)

        if callback:
            if inspect.iscoroutinefunction(callback):
                await callback(message, **kwargs)
            else:
                callback(message, **kwargs)

    @abstractmethod
    async def register_consumer(
        self, consumer: "BaseMessageQueueConsumer", **kwargs: Any
    ) -> Any:
        """Register consumer to start consuming messages."""

    @abstractmethod
    async def deregister_consumer(self, consumer: "BaseMessageQueueConsumer") -> Any:
        """Deregister consumer to stop publishing messages)."""

    async def get_consumers(
        self,
        message_type: str,
    ) -> List["BaseMessageQueueConsumer"]:
        """Gets list of consumers according to a message type."""
        raise NotImplementedError(
            "`get_consumers()` is not implemented for this class."
        )
