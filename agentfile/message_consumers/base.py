"""Message consumers."""

from abc import ABC, abstractmethod
from typing import Any, Type, TYPE_CHECKING
from agentfile.messages.base import BaseMessage

if TYPE_CHECKING:
    from agentfile.message_queues.base import BaseMessageQueue


class BaseMessageQueueConsumer(ABC):
    """Consumer of a MessageQueue."""

    id_: str
    message_type: Type[BaseMessage]

    @abstractmethod
    async def process_message(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Logic for processing message."""

    async def start_consuming(
        self, message_queue: BaseMessageQueue, **kwargs: Any
    ) -> None:
        """Begin consuming messages."""
        await message_queue.register_consumer(self, **kwargs)
