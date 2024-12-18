import asyncio
from logging import getLogger
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urljoin

import httpx
from fastapi import status

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
    default_start_consuming_callable,
)
from llama_deploy.message_consumers.remote import (
    RemoteMessageConsumer,
    RemoteMessageConsumerDef,
)
from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.types import PydanticValidatedUrl

from .config import SimpleMessageQueueConfig

logger = getLogger(__name__)


class SimpleRemoteClientMessageQueue(BaseMessageQueue):
    """Remote client to be used with a SimpleMessageQueue server."""

    base_url: PydanticValidatedUrl
    host: str
    port: Optional[int]
    client_kwargs: Optional[Dict] = None
    client: Optional[httpx.AsyncClient] = None
    raise_exceptions: bool = False

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, f"publish/{topic}")
        async with httpx.AsyncClient(**client_kwargs) as client:
            result = await client.post(url, json=message.model_dump())
        return result

    async def register_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        topic: str | None = None,
    ) -> StartConsumingCallable:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, "register_consumer")
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e
        async with httpx.AsyncClient(**client_kwargs) as client:
            result = await client.post(url, json=remote_consumer_def.model_dump())
        if result.status_code != status.HTTP_200_OK:
            logger.debug(
                f"An error occurred in registering consumer: {result.status_code}"
            )
            if self.raise_exceptions:
                raise ValueError(
                    f"An error occurred in registering consumer: {result.status_code}"
                )
        return default_start_consuming_callable

    async def deregister_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        deregister_consumer_url: str = "deregister_consumer",
    ) -> Any:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, deregister_consumer_url)
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e
        async with httpx.AsyncClient(**client_kwargs) as client:
            result = await client.post(url, json=remote_consumer_def.model_dump())
        return result

    async def get_consumers(
        self, message_type: str, get_consumers_url: str = "get_consumers"
    ) -> Sequence[BaseMessageQueueConsumer]:
        client_kwargs = self.client_kwargs or {}
        url = urljoin(self.base_url, f"{get_consumers_url}/{message_type}")
        async with httpx.AsyncClient(**client_kwargs) as client:
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

    async def launch_local(self) -> asyncio.Task:
        raise NotImplementedError("`launch_local()` is not implemented for this class.")

    async def launch_server(self) -> None:
        raise NotImplementedError(
            "`launch_server()` is not implemented for this class."
        )

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        raise NotImplementedError(
            "`cleanup_local()` is not implemented for this class."
        )

    def as_config(self) -> SimpleMessageQueueConfig:
        return SimpleMessageQueueConfig(host=self.host, port=self.port)
