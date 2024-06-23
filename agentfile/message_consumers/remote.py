import httpx
from pydantic import BaseModel, Field
from typing import Any, Optional

from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.messages import QueueMessage
from agentfile.types import generate_id


class RemoteMessageConsumerDef(BaseModel):
    id_: str = Field(default_factory=generate_id)
    message_type: str = Field(
        default="default", description="Type of the message to consume."
    )
    url: str = Field(default_factory=str, description="URL to send messages to.")
    client_kwargs: Optional[dict] = None


class RemoteMessageConsumer(BaseMessageQueueConsumer):
    url: str
    client_kwargs: Optional[dict] = None
    client: Optional[httpx.AsyncClient] = None

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)

        async with httpx.AsyncClient() as client:
            await client.post(self.url, json=message.model_dump())
