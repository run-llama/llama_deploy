"""Message consumers."""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Any, TYPE_CHECKING

from llama_agents.messages.base import QueueMessage
from llama_agents.types import generate_id

if TYPE_CHECKING:
    pass


class BaseMessageQueueConsumer(BaseModel, ABC):
    """Consumer of a MessageQueue."""

    id_: str = Field(default_factory=generate_id)
    message_type: str = Field(
        default="default", description="Type of the message to consume."
    )
    channel: Any = Field(
        default=None, description="The channel if any for which to receive messages."
    )

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
        await self.channel.start_consuming(self.process_message, self.message_type)
        print(f"channel: {self.channel}", flush=True)

    async def stop_consuming(
        self,
    ) -> None:
        """Stop consuming."""
        await self.channel.stop_consuming()
