import asyncio
import random
from logging import getLogger
from typing import Any, Dict, List

import httpx

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.messages.base import QueueMessage

from .config import SimpleMessageQueueConfig

logger = getLogger(__name__)


class SimpleMessageQueue(AbstractMessageQueue):
    """Remote client to be used with a SimpleMessageQueue server."""

    def __init__(
        self, config: SimpleMessageQueueConfig = SimpleMessageQueueConfig()
    ) -> None:
        self._config = config
        self._consumers: dict[str, dict[str, BaseMessageQueueConsumer]] = {}

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        """Sends a message to the SimpleMessageQueueServer."""
        url = f"{self._config.base_url}messages/{topic}"
        async with httpx.AsyncClient(**self._config.client_kwargs) as client:
            result = await client.post(url, json=message.model_dump())
        return result

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, topic: str | None = None
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        # register topic
        topic = topic or consumer.message_type

        if topic not in self._consumers:
            # call the server to create it
            url = f"{self._config.base_url}topics/{topic}"
            async with httpx.AsyncClient(**self._config.client_kwargs) as client:
                result = await client.post(url)
                result.raise_for_status()

            self._consumers[topic] = {}

        if consumer.id_ in self._consumers[topic]:
            msg = f"Consumer {consumer.id_} already registered for topic {topic}"
            raise ValueError(msg)

        self._consumers[topic][consumer.id_] = consumer
        logger.info(
            f"Consumer '{consumer.id_}' for type '{consumer.message_type}' on topic '{topic}' has been registered."
        )

        async def start_consuming_callable() -> None:
            """StartConsumingCallable.

            Consumer of this queue should call this in order to start consuming.
            """
            url = f"{self._config.base_url}messages/{topic}"
            async with httpx.AsyncClient(**self._config.client_kwargs) as client:
                while True:
                    try:
                        result = await client.get(url)
                        result.raise_for_status()
                        if result.json():
                            print(result.json())
                            message = QueueMessage.model_validate(result.json())
                            await consumer.process_message(message)
                        await asyncio.sleep(0.1)
                    except asyncio.exceptions.CancelledError:
                        break

        return start_consuming_callable

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        for topic, consumers in self._consumers.copy().items():
            if consumer.id_ in consumers:
                del self._consumers[topic][consumer.id_]

    async def _publish_to_consumer(
        self, message: QueueMessage, topic: str, **kwargs: Any
    ) -> Any:
        """Publish message to a consumer."""
        consumer = self._select_consumer(message, topic)
        try:
            await consumer.process_message(message, **kwargs)
            logger.info(f"Successfully published message '{message.type}' to consumer.")
        except Exception as e:
            logger.debug(
                f"Failed to publish message of type '{message.type}' to consumer. Message: {str(e)}"
            )
            raise

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

    def _select_consumer(
        self, message: QueueMessage, topic: str
    ) -> BaseMessageQueueConsumer:
        """Select a single consumer to publish a message to."""
        consumer_id = random.choice(list(self._consumers[topic].keys()))
        return self._consumers[topic][consumer_id]
