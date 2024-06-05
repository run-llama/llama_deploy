"""Message consumers."""

import uuid
from abc import ABC, abstractmethod
from typing import Any, Type, TYPE_CHECKING
from llama_index.core.bridge.pydantic import BaseModel, Field
from agentfile.messages.base import BaseMessage

if TYPE_CHECKING:
    from agentfile.message_queues.base import BaseMessageQueue


class BaseMessageQueueConsumer(BaseModel, ABC):
    """Consumer of a MessageQueue."""

    id_: str = Field(default_factory=uuid.uuid4)
    message_type: Type[BaseMessage] = Field(default=BaseMessage)

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def _process_message(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Subclasses should implement logic here."""

    async def process_message(self, message: BaseMessage, **kwargs: Any) -> Any:
        """Logic for processing message."""
        if not isinstance(message, self.message_type):
            raise ValueError("Consumer cannot process the given kind of Message.")
        return self._process_message(message, **kwargs)

    async def start_consuming(
        self, message_queue: "BaseMessageQueue", **kwargs: Any
    ) -> None:
        """Begin consuming messages."""
        await message_queue.register_consumer(self, **kwargs)
