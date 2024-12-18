import asyncio
from logging import getLogger
from typing import Any, Dict, List, Sequence

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
from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.messages.base import QueueMessage

from .config import SimpleMessageQueueConfig

logger = getLogger(__name__)


class SimpleRemoteClientMessageQueue(AbstractMessageQueue):
    """Remote client to be used with a SimpleMessageQueue server."""

    def __init__(self, config: SimpleMessageQueueConfig) -> None:
        self._config = config

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        url = f"{self._config.base_url}publish/{topic}"
        async with httpx.AsyncClient(**self._config.client_kwargs) as client:
            result = await client.post(url, json=message.model_dump())
        return result

    async def register_consumer(
        self,
        consumer: BaseMessageQueueConsumer,
        topic: str | None = None,
    ) -> StartConsumingCallable:
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e

        async with httpx.AsyncClient(**self._config.client_kwargs) as client:
            url = f"{self._config.base_url}register_consumer"
            result = await client.post(url, json=remote_consumer_def.model_dump())

        if result.status_code != status.HTTP_200_OK:
            msg = f"An error occurred in registering consumer: {result.status_code}"
            logger.debug(msg)
            if self._config.raise_exceptions:
                raise ValueError(msg)

        return default_start_consuming_callable

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        try:
            remote_consumer_def = RemoteMessageConsumerDef(**consumer.model_dump())
        except Exception as e:
            raise ValueError(
                "Unable to convert consumer to RemoteMessageConsumer"
            ) from e

        async with httpx.AsyncClient(**self._config.client_kwargs) as client:
            url = f"{self._config.base_url}deregister_consumer"
            result = await client.post(url, json=remote_consumer_def.model_dump())

        return result

    async def get_consumers(
        self, message_type: str
    ) -> Sequence[BaseMessageQueueConsumer]:
        async with httpx.AsyncClient(**self._config.client_kwargs) as client:
            url = f"{self._config.base_url}get_consumers/{message_type}"
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
        return self._config
