"""Remote message queue."""
import asyncio
import httpx

from logging import getLogger
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.message_consumers.base import BaseMessageQueueConsumer
from llama_agents.messages import QueueMessage

logger = getLogger(__name__)


class RemoteClientMessageQueue(BaseMessageQueue):
    base_url: str
    client_kwargs: Optional[Dict] = None
    client: Optional[httpx.AsyncClient] = None

    async def _publish(
        self, message: QueueMessage, publish_url: str = "publish", **kwargs: Any
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = urljoin(self.base_url, publish_url)
        async with httpx.AsyncClient() as client:
            await client.post(url, json=message.model_dump())

    async def register_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        register_consumer_url: str = "register_consumer",
        **kwargs: Any,
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = urljoin(self.base_url, register_consumer_url)
        async with httpx.AsyncClient() as client:
            await client.post(url, json=consumer.model_dump())

    async def deregister_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        deregister_consumer_url: str = "deregister_consumer",
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = urljoin(self.base_url, deregister_consumer_url)
        async with httpx.AsyncClient() as client:
            await client.post(url, json=consumer.model_dump())

    async def get_consumers(
        self, message_type: str, get_consumers_url: str = "get_consumers"
    ) -> List[BaseMessageQueueConsumer]:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = urljoin(self.base_url, get_consumers_url)
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json={"message_type": message_type})
        return res

    async def processing_loop(self) -> None:
        raise NotImplementedError(
            "`procesing_loop()` is not implemented for this class."
        )

    async def launch_local(self) -> asyncio.Task:
        raise NotImplementedError("`launch_local()` is not implemented for this class.")

    async def launch_server(self) -> None:
        raise NotImplementedError(
            "`launch_server()` is not implemented for this class."
        )
