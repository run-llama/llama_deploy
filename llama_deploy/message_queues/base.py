"""Message queue module."""

import inspect
from abc import ABC, abstractmethod
from logging import getLogger
from typing import Any, AsyncIterator, Awaitable, Callable

from pydantic import BaseModel

from llama_deploy.messages.base import QueueMessage

logger = getLogger(__name__)


PublishCallback = (
    Callable[[QueueMessage], Any] | Callable[[QueueMessage], Awaitable[Any]]
)


class AbstractMessageQueue(ABC):
    """Message broker interface between publisher and consumer."""

    @abstractmethod
    async def _publish(
        self, message: QueueMessage, topic: str, create_topic: bool
    ) -> Any:
        """Subclasses implement publish logic here."""

    async def publish(
        self,
        message: QueueMessage,
        topic: str,
        callback: PublishCallback | None = None,
        create_topic: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Send message to a consumer."""
        logger.info(
            f"Publishing message of type '{message.type}' with action '{message.action}' to topic '{topic}'"
        )
        logger.debug(f"Message: {message.model_dump()}")

        message.stats.publish_time = message.stats.timestamp_str()
        await self._publish(message, topic, create_topic)

        if callback:
            if inspect.iscoroutinefunction(callback):
                await callback(message, **kwargs)
            else:
                callback(message, **kwargs)

    @abstractmethod
    async def cleanup(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        """Perform any cleanup before shutting down."""

    @abstractmethod
    def as_config(self) -> BaseModel:
        """Returns the config dict to reconstruct the message queue."""

    async def get_message(self, topic: str) -> AsyncIterator[QueueMessage]:
        if False:
            # This is to help type checkers
            yield
