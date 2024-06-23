"""Remote message queue."""

import httpx
import logging

from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from agentfile.message_queues.base import BaseMessageQueue
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.message_consumers.remote import (
    RemoteMessageConsumerDef,
    RemoteMessageConsumer,
)
from agentfile.messages import QueueMessage
from agentfile.types import PydanticValidatedUrl

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


class RemoteClientMessageQueue(BaseMessageQueue):
    base_url: PydanticValidatedUrl
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
    ) -> httpx.Response:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = urljoin(self.base_url, register_consumer_url)
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e
        async with httpx.AsyncClient() as client:
            result = await client.post(url, json=remote_consumer_def.model_dump())
        return result

    async def deregister_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        deregister_consumer_url: str = "deregister_consumer",
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = urljoin(self.base_url, deregister_consumer_url)
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e
        async with httpx.AsyncClient() as client:
            result = await client.post(url, json=remote_consumer_def.model_dump())
        return result

    async def get_consumers(
        self, message_type: str, get_consumers_url: str = "get_consumers"
    ) -> List[BaseMessageQueueConsumer]:
        client_kwargs = self.client_kwargs or {}
        client = self.client or httpx.AsyncClient(**client_kwargs)
        url = urljoin(self.base_url, f"{get_consumers_url}/{message_type}")
        logger.info(f"url: {url}")
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
        if res.status_code == 200:
            remote_consumer_defs = res.json()
            consumers = [RemoteMessageConsumer(**el) for el in remote_consumer_defs]
        else:
            consumers = []
        return consumers

    async def processing_loop(self) -> None:
        raise NotImplementedError(
            "`procesing_loop()` is not implemented for this class."
        )

    async def launch_local(self) -> None:
        raise NotImplementedError("`launch_local()` is not implemented for this class.")

    async def launch_server(self) -> None:
        raise NotImplementedError(
            "`launch_server()` is not implemented for this class."
        )
