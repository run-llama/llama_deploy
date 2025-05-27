import asyncio
from logging import getLogger
from typing import Any, AsyncIterator, Dict

import httpx

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
        self._topics: set[str] = set()

    async def _publish(
        self, message: QueueMessage, topic: str, create_topic: bool
    ) -> Any:
        """Sends a message to the SimpleMessageQueueServer."""
        if topic not in self._topics:
            # call the server to create it
            url = f"{self._config.base_url}topics/{topic}"
            async with httpx.AsyncClient(**self._config.client_kwargs) as client:
                result = await client.post(url)
                result.raise_for_status()
                self._topics.add(topic)

        url = f"{self._config.base_url}messages/{topic}"
        async with httpx.AsyncClient(**self._config.client_kwargs) as client:
            result = await client.post(url, json=message.model_dump())
        return result

    async def get_messages(self, topic: str) -> AsyncIterator[QueueMessage]:
        url = f"{self._config.base_url}messages/{topic}"
        client = httpx.AsyncClient(**self._config.client_kwargs)
        while True:
            try:
                result = await client.get(url)
                result.raise_for_status()
                if result.json():
                    yield QueueMessage.model_validate(result.json())
                await asyncio.sleep(0.1)

            except httpx.HTTPError as e:
                logger.debug(f"HTTP error occurred while fetching messages: {e}")
                await asyncio.sleep(1)  # Back off on errors
                continue

            except Exception as e:
                logger.error(f"Unexpected error while fetching messages: {e}")
                await asyncio.sleep(1)  # Back off on errors
                continue

    async def cleanup(self, *args: Any, **kwargs: Dict[str, Any]) -> None:
        # Nothing to clean up
        pass

    def as_config(self) -> SimpleMessageQueueConfig:
        return self._config
