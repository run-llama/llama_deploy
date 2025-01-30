"""Redis Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.messages.base import QueueMessage

logger = getLogger(__name__)


class RedisMessageQueueConfig(BaseSettings):
    """Redis message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    type: Literal["redis"] = Field(default="redis", exclude=True)
    url: str = "redis://localhost:6379"
    host: str | None = None
    port: int | None = None
    db: int | None = None
    username: str | None = None
    password: str | None = None
    ssl: bool | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.host and self.port:
            scheme = "rediss" if self.ssl else "redis"
            auth = (
                f"{self.username}:{self.password}@"
                if self.username and self.password
                else ""
            )
            self.url = f"{scheme}://{auth}{self.host}:{self.port}/{self.db or ''}"


class RedisConsumerMetadata(BaseModel):
    message_type: str
    start_consuming_callable: StartConsumingCallable
    pubsub: Any = None
    topic: str


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
        self._consumers: dict[str, RedisConsumerMetadata] = {}

        try:
            from redis.asyncio import Redis

            self._redis: Redis = Redis.from_url(self._config.url)
        except ImportError:
            msg = "Missing redis optional dependency. Please install by running `pip install llama-deploy[redis]`."
            raise ValueError(msg)

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        """Publish message to the Redis channel."""
        message_json = json.dumps(message.model_dump())
        result = await self._redis.publish(topic, message_json)
        logger.info(
            f"Published message {message.id_} to topic {topic} with {result} subscribers"
        )
        return result

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, topic: str
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        if consumer.id_ in self._consumers:
            logger.debug(
                f"Consumer {consumer.id_} already registered for topic {topic}",
            )
            return self._consumers[consumer.id_].start_consuming_callable

        pubsub = self._redis.pubsub()
        await pubsub.subscribe(topic)

        async def start_consuming_callable() -> None:
            """StartConsumingCallable.

            Consumer of this queue should call this in order to start consuming.
            """
            try:
                while True:
                    message = await pubsub.get_message(ignore_subscribe_messages=True)
                    if message:
                        decoded_message = json.loads(message["data"])
                        queue_message = QueueMessage.model_validate(decoded_message)
                        await consumer.process_message(queue_message)
                    await asyncio.sleep(0.01)
            finally:
                return

        logger.info(
            f"Registered consumer {consumer.id_} for topic {topic}",
        )

        self._consumers[consumer.id_] = RedisConsumerMetadata(
            message_type=consumer.message_type,
            start_consuming_callable=start_consuming_callable,
            pubsub=pubsub,
            topic=topic,
        )

        return start_consuming_callable

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister a consumer."""
        consumer_metadata = self._consumers.pop(consumer.id_, None)
        if consumer_metadata is not None:
            await consumer_metadata.pubsub.unsubscribe(consumer_metadata.topic)
            logger.info(
                f"Deregistered consumer {consumer.id_} for topic {consumer_metadata.topic}",
            )

    async def cleanup(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        """Perform any cleanup before shutting down."""
        for consumer_metadata in self._consumers.values():
            if consumer_metadata.pubsub:
                await consumer_metadata.pubsub.unsubscribe()
                await consumer_metadata.pubsub.aclose()

        # Clear consumers
        self._consumers = {}

        # Close main Redis connection
        await self._redis.aclose()  # type: ignore  # mypy doesn't see the async method for some reason

    def as_config(self) -> BaseModel:
        return self._config
