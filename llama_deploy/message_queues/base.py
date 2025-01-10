"""Message queue module."""

import inspect
from abc import ABC, abstractmethod
from logging import getLogger
from typing import (
    Any,
    Awaitable,
    Callable,
    Sequence,
)

from pydantic import BaseModel

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.messages.base import QueueMessage

logger = getLogger(__name__)


PublishCallback = (
    Callable[[QueueMessage], Any] | Callable[[QueueMessage], Awaitable[Any]]
)


class AbstractMessageQueue(ABC):
    """Message broker interface between publisher and consumer."""

    @abstractmethod
    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        """Subclasses implement publish logic here."""

    async def publish(
        self,
        message: QueueMessage,
        topic: str,
        callback: PublishCallback | None = None,
        **kwargs: Any,
    ) -> Any:
        """Send message to a consumer."""
        logger.info(
            f"Publishing message of type '{message.type}' with action '{message.action}' to topic '{topic}'"
        )
        logger.debug(f"Message: {message.model_dump()}")

        message.stats.publish_time = message.stats.timestamp_str()
        await self._publish(message, topic)

        if callback:
            if inspect.iscoroutinefunction(callback):
                await callback(message, **kwargs)
            else:
                callback(message, **kwargs)

    @abstractmethod
    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, topic: str
    ) -> StartConsumingCallable:
        """Register consumer to start consuming messages."""

    @abstractmethod
    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister consumer to stop publishing messages)."""

    async def get_consumers(
        self, message_type: str
    ) -> Sequence[BaseMessageQueueConsumer]:
        """Gets list of consumers according to a message type."""
        raise NotImplementedError(
            "`get_consumers()` is not implemented for this class."
        )

    @abstractmethod
    async def cleanup(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        """Perform any cleanup before shutting down."""

    @abstractmethod
    def as_config(self) -> BaseModel:
        """Returns the config dict to reconstruct the message queue."""
