from typing import Any, Optional

import httpx
from pydantic import BaseModel, Field

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.messages import QueueMessage
from llama_deploy.types import generate_id


class RemoteMessageConsumerDef(BaseModel):
    """Definition for a RemoteMessageConsumer.

    Helps describe the configuration for a RemoteMessageConsumer.
    """

    id_: str = Field(default_factory=generate_id)
    message_type: str = Field(
        default="default", description="Type of the message to consume."
    )
    url: str = Field(default_factory=str, description="URL to send messages to.")
    client_kwargs: Optional[dict] = None


class RemoteMessageConsumer(BaseMessageQueueConsumer):
    """Consumer of a MessageQueue that sends messages to a remote service.

    For each message, it will send the message to the given URL.
    """

    url: str
    client_kwargs: Optional[dict] = None
    client: Optional[httpx.AsyncClient] = None

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        client_kwargs = self.client_kwargs or {}

        async with httpx.AsyncClient(**client_kwargs) as client:
            await client.post(self.url, json=message.model_dump())
