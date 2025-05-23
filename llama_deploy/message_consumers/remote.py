from typing import Any, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

from llama_deploy.messages import QueueMessage
from llama_deploy.types import generate_id


class RemoteMessageConsumer(BaseModel):
    """Consumer of a MessageQueue that sends messages to a remote service.

    For each message, it will send the message to the given URL.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id_: str = Field(default_factory=generate_id)
    url: str = ""
    client_kwargs: Optional[dict] = None
    client: Optional[httpx.AsyncClient] = None
    message_type: str = Field(
        default="default", description="Type of the message to consume."
    )

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        client_kwargs = self.client_kwargs or {}

        async with httpx.AsyncClient(**client_kwargs) as client:
            await client.post(self.url, json=message.model_dump())

    async def process_message(self, message: QueueMessage, **kwargs: Any) -> Any:
        """Logic for processing message."""
        if message.type != self.message_type:
            msg = f"Consumer cannot process messages of type '{message.type}'."
            raise ValueError(msg)
        return await self._process_message(message, **kwargs)
