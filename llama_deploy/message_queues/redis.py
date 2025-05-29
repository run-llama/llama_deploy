"""Redis Message Queue."""

import json
from logging import getLogger
from typing import Any, AsyncIterator, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.types import QueueMessage

logger = getLogger(__name__)


class RedisMessageQueueConfig(BaseSettings):
    """Redis message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    type: Literal["redis"] = Field(default="redis")
    url: str = "redis://localhost:6379"
    host: str | None = None
    port: int | None = None
    db: int | None = None
    username: str | None = None
    password: str | None = None
    ssl: bool | None = None
    exclusive_mode: bool = False

    def model_post_init(self, __context: Any) -> None:
        if self.host and self.port:
            scheme = "rediss" if self.ssl else "redis"
            auth = (
                f"{self.username}:{self.password}@"
                if self.username and self.password
                else ""
            )
            self.url = f"{scheme}://{auth}{self.host}:{self.port}/{self.db or ''}"


class RedisMessageQueue(AbstractMessageQueue):
    """Redis integration for message queue.

    This class uses Redis Pub/Sub functionality for message distribution.

    Examples:
        ```python
        from llama_deploy.message_queues.redis import RedisMessageQueue

        message_queue = RedisMessageQueue()  # uses the default url
        ```
    """

    def __init__(self, config: RedisMessageQueueConfig | None = None) -> None:
        self._config = config or RedisMessageQueueConfig()

        try:
            from redis.asyncio import Redis

            self._redis: Redis = Redis.from_url(self._config.url)
        except ImportError:
            msg = "Missing redis optional dependency. Please install by running `pip install llama-deploy[redis]`."
            raise ValueError(msg)

    async def _publish(
        self, message: QueueMessage, topic: str, create_topic: bool
    ) -> Any:
        """Publish message to the Redis channel."""
        message_json = json.dumps(message.model_dump())
        result = await self._redis.publish(topic, message_json)
        logger.info(
            f"Published message {message.id_} to topic {topic} with {result} subscribers"
        )
        return result

    async def get_messages(self, topic: str) -> AsyncIterator[QueueMessage]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(topic)

        processed_message_key = f"{topic}.processed_messages"
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    decoded_message = json.loads(message["data"])
                    queue_message = QueueMessage.model_validate(decoded_message)

                    # Deduplication check
                    if self._config.exclusive_mode:
                        new_message = await self._redis.sadd(  # type: ignore
                            processed_message_key, queue_message.id_
                        )
                        if not new_message:
                            logger.debug(
                                f"Skipping message {queue_message.id_} as it has "
                                "already been consumed."
                            )
                            continue

                        # Set expiration for deduplication key. Expire processed messages
                        # in 5 minutes.
                        await self._redis.expire(processed_message_key, 300, nx=True)

                    yield queue_message
        finally:
            return

    async def cleanup(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        # Close main Redis connection
        await self._redis.aclose()  # type: ignore

    def as_config(self) -> BaseModel:
        return self._config
