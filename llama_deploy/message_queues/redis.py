"""Redis Message Queue."""

import asyncio
import json
from pydantic import PrivateAttr, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from logging import getLogger
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)

if TYPE_CHECKING:
    import redis.asyncio as redis

logger = getLogger(__name__)

DEFAULT_URL = "redis://localhost:6379"


class RedisMessageQueueConfig(BaseSettings):
    """Redis message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="REDIS_")

    url: str = DEFAULT_URL
    host: Optional[str] = None
    port: Optional[int] = None
    db: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    ssl: Optional[bool] = None

    def model_post_init(self, __context: Any) -> None:
        if self.host and self.port:
            scheme = "rediss" if self.ssl else "redis"
            auth = (
                f"{self.username}:{self.password}@"
                if self.username and self.password
                else ""
            )
            self.url = f"{scheme}://{auth}{self.host}:{self.port}/{self.db or ''}"


async def _establish_connection(url: str) -> "redis.Redis":
    try:
        import redis.asyncio as redis
    except ImportError:
        raise ValueError(
            "Missing redis optional dep. Please install by running `pip install llama-deploy[redis]`."
        )
    return redis.from_url(
        url,
    )


class RedisConsumerMetadata(BaseModel):
    message_type: str
    start_consuming_callable: StartConsumingCallable
    pubsub: Any = None


class RedisMessageQueue(BaseMessageQueue):
    """Redis integration for message queue.

    This class uses Redis Pub/Sub functionality for message distribution.

    Attributes:
        url (str): The Redis URL string to connect to the Redis server
        redis (redis.Redis): The Redis connection

    Examples:
        ```python
        from llama_deploy.message_queues.redis import RedisMessageQueue

        message_queue = RedisMessageQueue()  # uses the default url
        ```
    """

    url: str = DEFAULT_URL
    _redis: Optional["redis.Redis"] = PrivateAttr(None)

    def __init__(
        self,
        url: str = DEFAULT_URL,
        redis: Optional["redis.Redis"] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(url=url)
        self._redis = redis
        self._consumers: Dict[str, RedisConsumerMetadata] = {}

    @classmethod
    def from_url_params(
        cls,
        host: str,
        port: int = 6379,
        db: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ssl: bool = False,
    ) -> "RedisMessageQueue":
        """Convenience constructor from url params."""
        scheme = "rediss" if ssl else "redis"
        auth = f"{username}:{password}@" if username and password else ""
        url = f"{scheme}://{auth}{host}:{port}/{db}"
        return cls(url=url)

    async def new_connection(self) -> "redis.Redis":
        """Returns a new connection to the Redis server."""
        if self._redis is None:
            self._redis = await _establish_connection(self.url)
        return self._redis

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to the Redis channel."""
        redis = await self.new_connection()
        message_json = json.dumps(message.model_dump())
        result = await redis.publish(message.type, message_json)
        logger.info(
            f"Published message {message.id_} to {message.type} channel with {result} subscribers"
        )
        return result

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        if consumer.id_ in self._consumers:
            logger.debug(
                f"Consumer {consumer.id_} already registered for {consumer.message_type} messages",
            )
            return self._consumers[consumer.id_].start_consuming_callable

        redis = await self.new_connection()
        pubsub = redis.pubsub()
        await pubsub.subscribe(consumer.message_type)

        async def start_consuming_callable() -> None:
            """StartConsumingCallable.

            Consumer of this queue should call this in order to start consuming.
            """
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    decoded_message = json.loads(message["data"])
                    queue_message = QueueMessage.model_validate(decoded_message)
                    await consumer.process_message(queue_message)
                await asyncio.sleep(0.01)

        logger.info(
            f"Registered consumer {consumer.id_} for {consumer.message_type} messages",
        )

        self._consumers[consumer.id_] = RedisConsumerMetadata(
            message_type=consumer.message_type,
            start_consuming_callable=start_consuming_callable,
            pubsub=pubsub,
        )

        return start_consuming_callable

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister a consumer."""
        if consumer.id_ in self._consumers:
            await self._consumers[consumer.id_].pubsub.unsubscribe(
                consumer.message_type
            )
            del self._consumers[consumer.id_]
            logger.info(
                f"Deregistered consumer {consumer.id_} for {consumer.message_type} messages",
            )

    async def processing_loop(self) -> None:
        """A loop for getting messages from queues and sending to consumer.

        Not relevant for this class as Redis uses pub/sub model.
        """
        pass

    async def launch_local(self) -> asyncio.Task:
        """Launch the message queue locally, in-process.

        Launches a dummy task.
        """
        return asyncio.create_task(self.processing_loop())

    async def launch_server(self) -> None:
        """Launch the message queue server.

        Not relevant for this class. Redis server should be running separately."""
        pass

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        """Perform any cleanup before shutting down."""
        if self._redis:
            await self._redis.close()

        self._redis = None
        self._consumers = {}

    def as_config(self) -> BaseModel:
        return RedisMessageQueueConfig(url=self.url)
