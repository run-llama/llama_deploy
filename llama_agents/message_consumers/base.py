"""Message consumers."""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Any, Awaitable, Callable, Optional, TYPE_CHECKING

from llama_agents.messages.base import QueueMessage
from llama_agents.types import generate_id

if TYPE_CHECKING:
    pass

StartConsumingCallable = Callable[..., Awaitable[Any]]


class BaseMessageQueueConsumer(BaseModel, ABC):
    """Consumer of a MessageQueue."""

    id_: str = Field(default_factory=generate_id)
    message_type: str = Field(
        default="default", description="Type of the message to consume."
    )
    channel: Any = Field(
        default=None, description="The channel if any for which to receive messages."
    )
    consuming_callable: Optional[StartConsumingCallable] = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Subclasses should implement logic here."""

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Logic for processing message."""
        if message.type != self.message_type:
            raise ValueError("Consumer cannot process the given kind of Message.")
        return await self._process_message(message, **kwargs)

    async def start_consuming(
        self,
    ) -> None:
        """Begin consuming messages."""
        if self.consuming_callable:
            await self.consuming_callable()
