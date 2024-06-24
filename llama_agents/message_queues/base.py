"""Message queue module."""
import asyncio
import inspect

from abc import ABC, abstractmethod
from logging import getLogger
from pydantic import BaseModel
from typing import Any, List, Optional, Protocol, TYPE_CHECKING

from llama_agents.messages.base import QueueMessage

if TYPE_CHECKING:
    from llama_agents.message_consumers.base import BaseMessageQueueConsumer

logger = getLogger(__name__)


class MessageProcessor(Protocol):
    """Protocol for a callable that processes messages."""

    def __call__(self, message: QueueMessage, **kwargs: Any) -> None:
        ...


class PublishCallback(Protocol):
    """Protocol for a callable that processes messages.

    TODO: Variant for Async Publish Callback.
    """

    def __call__(self, message: QueueMessage, **kwargs: Any) -> None:
        ...


class BaseMessageQueue(BaseModel, ABC):
    """Message broker interface between publisher and consumer."""

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def _publish(self, message: QueueMessage) -> Any:
        """Subclasses implement publish logic here."""
        ...

    async def publish(
        self,
        message: QueueMessage,
        callback: Optional[PublishCallback] = None,
        **kwargs: Any,
    ) -> Any:
        """Send message to a consumer."""
        logger.info(
            f"Publishing message to '{message.type}' with action '{message.action}'"
        )
        logger.debug(f"Message: {message.model_dump()}")

        message.stats.publish_time = message.stats.timestamp_str()
        await self._publish(message)

        if callback:
            if inspect.iscoroutinefunction(callback):
                await callback(message, **kwargs)
            else:
                callback(message, **kwargs)

    @abstractmethod
    async def register_consumer(
        self,
        consumer: "BaseMessageQueueConsumer",
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

    @abstractmethod
    async def processing_loop(self) -> None:
        """The processing loop for the service."""
        ...

    @abstractmethod
    async def launch_local(self) -> asyncio.Task:
        """Launch the service in-process."""
        ...

    @abstractmethod
    async def launch_server(self) -> None:
        """Launch the service as a server."""
        ...
