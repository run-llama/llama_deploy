"""Remote message queue."""

import httpx
import logging
from typing import Any, Dict, List, Optional

from agentfile.message_queues.base import BaseMessageQueue
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.messages import QueueMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class RemoteMessageQueue(BaseMessageQueue):
    base_url: str
    client_kwargs: Optional[Dict] = None
    client: Optional[httpx.AsyncClient] = None

    async def _publish(self, message: QueueMessage, **kwargs: Any) -> Any:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = f"{self.base_url}/publish"
        async with httpx.AsyncClient() as client:
            await client.post(url, json=message.model_dump())

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, **kwargs: Any
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = f"{self.base_url}/register_consumer"
        async with httpx.AsyncClient() as client:
            await client.post(url, json=consumer.model_dump())

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = f"{self.base_url}/deregister_consumer"
        async with httpx.AsyncClient() as client:
            await client.post(url, json=consumer.model_dump())

    async def get_consumers(self, message_type: str) -> List[BaseMessageQueueConsumer]:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = f"{self.base_url}/get_consumers"
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json={"message_type": message_type})
        return res

    async def processing_loop(self) -> None:
        pass

    async def launch_local(self) -> None:
        pass

    def launch_server(self) -> None:
        pass
