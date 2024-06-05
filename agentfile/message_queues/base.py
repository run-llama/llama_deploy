"""Message queue module."""

from abc import abstractmethod
from typing import Any, Dict, Protocol, Type
from agentfile.messages.base import BaseMessage
from agentfile.message_consumers.base import BaseMessageQueueConsumer


class MessageProcessor(Protocol):
    """Protocol for a callable that processes messages."""

    def __call__(self, message: BaseMessage, **kwargs: Any) -> None:
        ...


class BaseMessageQueue:
    """Message broker interface between publisher and consumer."""

    consumers: Dict[str, BaseMessageQueueConsumer]  # Message Class Name as key

    @abstractmethod
    def _publish(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Subclasses implement publish logic here."""
        ...

    def publish(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Send message to a consumer."""
        self._publish(message, **kwargs)

    @abstractmethod
    def register_consumer(
        self,
        consumer_id: str,
        message_type: Type[BaseMessage],
        processor: MessageProcessor,
        **kwargs: Any
    ) -> Any:
        """Register consumer to start consuming messages."""

    @abstractmethod
    def deregister_consumer(self, consumer_id: str) -> Any:
        """Deregister consumer to stop publishing messages)."""
