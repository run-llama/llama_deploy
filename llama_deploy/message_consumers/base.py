"""Message consumers."""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Callable, TYPE_CHECKING, Coroutine

from llama_deploy.messages.base import QueueMessage
from llama_deploy.types import generate_id

if TYPE_CHECKING:
    pass

StartConsumingCallable = Callable[..., Coroutine[Any, Any, None]]


async def default_start_consuming_callable() -> None:
    pass


class BaseMessageQueueConsumer(BaseModel, ABC):
    """Consumer of a MessageQueue.

    Process messages from a MessageQueue for a specific message type.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
    id_: str = Field(default_factory=generate_id)
    message_type: str = Field(
        default="default", description="Type of the message to consume."
    )
    channel: Any = Field(
        default=None, description="The channel if any for which to receive messages."
    )
    consuming_callable: StartConsumingCallable = Field(
        default=default_start_consuming_callable
    )

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
        await self.consuming_callable()
