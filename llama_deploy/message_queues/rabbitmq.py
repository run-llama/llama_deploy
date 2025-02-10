"""RabbitMQ Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.messages.base import QueueMessage

if TYPE_CHECKING:  # pragma: no cover
    from aio_pika import Connection

logger = getLogger(__name__)


DEFAULT_URL = "amqp://guest:guest@localhost/"
DEFAULT_EXCHANGE_NAME = "llama-deploy"


class RabbitMQMessageQueueConfig(BaseSettings):
    """RabbitMQ message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_")

    type: Literal["rabbitmq"] = Field(default="rabbitmq", exclude=True)
    url: str = DEFAULT_URL
    exchange_name: str = DEFAULT_EXCHANGE_NAME
    username: str | None = None
    password: str | None = None
    host: str | None = None
    port: int | None = None
    vhost: str | None = None
    secure: bool | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.username and self.password and self.host:
            scheme = "amqps" if self.secure else "amqp"
            self.url = f"{scheme}://{self.username}:{self.password}@{self.host}"
            if self.port:
                self.url += f":{self.port}"
            elif self.vhost:
                self.url += f"/{self.vhost}"


async def _establish_connection(url: str) -> "Connection":
    try:
        import aio_pika
        from aio_pika import Connection
    except ImportError:
        raise ValueError(
            "Missing pika optional dep. Please install by running `pip install llama-deploy[rabbimq]`."
        )
    return cast(Connection, await aio_pika.connect(url))


class RabbitMQMessageQueue(AbstractMessageQueue):
    """RabbitMQ integration with aio-pika client.

    This class creates a Work (or Task) Queue. For more information on Work Queues
    with RabbitMQ see the pages linked below:
        1. https://aio-pika.readthedocs.io/en/latest/rabbitmq-tutorial/2-work-queues.html
        2. https://aio-pika.readthedocs.io/en/latest/rabbitmq-tutorial/3-publish-subscribe.html

    Connections are established by url that use [amqp uri scheme](https://www.rabbitmq.com/docs/uri-spec#the-amqp-uri-scheme):

    ```
    amqp_URI       = "amqp://" amqp_authority [ "/" vhost ] [ "?" query ]
    amqp_authority = [ amqp_userinfo "@" ] host [ ":" port ]
    amqp_userinfo  = username [ ":" password ]
    username       = *( unreserved / pct-encoded / sub-delims )
    password       = *( unreserved / pct-encoded / sub-delims )
    vhost          = segment
    ```

    The Work Queue created has the following properties:
        - Exchange with name self.exchange
        - Messages are published to this queue through the exchange
        - Consumers are bound to the exchange and have queues based on their
            message type
        - Round-robin dispatching: with multiple consumers listening to the same
            queue, only one consumer will be chosen dictated by sequence.

    Attributes:
        url (str): The amqp url string to connect to the RabbitMQ server
        exchange_name (str): The name to give to the so-called exchange within
            RabbitMQ AMQP 0-9 protocol.

    Examples:
        ```python
        from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueue

        message_queue = RabbitMQMessageQueue()  # uses the default url
        ```
    """

    def __init__(
        self,
        config: RabbitMQMessageQueueConfig | None = None,
        url: str = DEFAULT_URL,
        exchange_name: str = DEFAULT_EXCHANGE_NAME,
        **kwargs: Any,
    ) -> None:
        self._config = config or RabbitMQMessageQueueConfig()
        self._registered_topics: set[str] = set()

    @classmethod
    def from_url_params(
        cls,
        username: str,
        password: str,
        host: str,
        vhost: str = "",
        port: int | None = None,
        secure: bool = False,
        exchange_name: str = DEFAULT_EXCHANGE_NAME,
    ) -> "RabbitMQMessageQueue":
        """Convenience constructor from url params.

        Args:
            username (str): username for the amqp authority
            password (str): password for the amqp authority
            host (str): host for rabbitmq server
            port (int | None, optional): port for rabbitmq server. Defaults to None.
            secure (bool, optional): Whether or not to use SSL. Defaults to False.
            exchange_name (str, optional): The exchange name. Defaults to DEFAULT_EXCHANGE_NAME.

        Returns:
            RabbitMQMessageQueue: A RabbitMQ MessageQueue integration.
        """
        if not secure:
            if port:
                url = f"amqp://{username}:{password}@{host}:{port}/{vhost}"
            else:
                url = f"amqp://{username}:{password}@{host}/{vhost}"
        else:
            if port:
                url = f"amqps://{username}:{password}@{host}:{port}/{vhost}"
            else:
                url = f"amqps://{username}:{password}@{host}/{vhost}"
        return cls(RabbitMQMessageQueueConfig(url=url, exchange_name=exchange_name))

    async def new_connection(self) -> "Connection":
        """Returns a new connection to the RabbitMQ server."""
        return await _establish_connection(self._config.url)

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        """Publish message to the queue."""
        from aio_pika import DeliveryMode, ExchangeType
        from aio_pika import Message as AioPikaMessage

        connection = await _establish_connection(self._config.url)

        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                self._config.exchange_name,
                ExchangeType.DIRECT,
            )
            message_body = json.dumps(message.model_dump()).encode("utf-8")

            aio_pika_message = AioPikaMessage(
                message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
            )
            # Sending the message
            await exchange.publish(aio_pika_message, routing_key=topic)
            logger.info(f"published message {message.id_} to {topic}")

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, topic: str
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        from aio_pika import Channel, ExchangeType, IncomingMessage, Queue
        from aio_pika.abc import AbstractIncomingMessage

        connection = await _establish_connection(self._config.url)
        async with connection:
            channel = cast(Channel, await connection.channel())
            exchange = await channel.declare_exchange(
                self._config.exchange_name,
                ExchangeType.DIRECT,
            )
            queue = cast(Queue, await channel.declare_queue(name=topic))
            await queue.bind(exchange)

        self._registered_topics.add(topic or consumer.message_type)
        logger.info(
            f"Registered consumer {consumer.id_} for topic: {topic}",
        )

        async def start_consuming_callable() -> None:
            """StartConsumingCallable.

            Consumer of this queue, should call this in order to start consuming.
            """

            async def on_message(message: AbstractIncomingMessage) -> None:
                message = cast(IncomingMessage, message)
                async with message.process():
                    decoded_message = json.loads(message.body.decode("utf-8"))
                    queue_message = QueueMessage.model_validate(decoded_message)
                    await consumer.process_message(queue_message)

            # The while loop will reconnect if the connection is lost
            while True:
                connection = await _establish_connection(self._config.url)
                try:
                    async with connection:
                        channel = await connection.channel()
                        exchange = await channel.declare_exchange(
                            self._config.exchange_name,
                            ExchangeType.DIRECT,
                        )
                        queue = cast(Queue, await channel.declare_queue(name=topic))
                        await queue.bind(exchange)
                        await queue.consume(on_message)
                        await asyncio.Future()
                except asyncio.CancelledError:
                    logger.info(
                        f"Cancellation requested, exiting consumer {consumer.id_} for topic: {topic}"
                    )
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    # Wait before reconnecting. Ideally we'd want exponential backoff here.
                    await asyncio.sleep(10)
                finally:
                    if connection:
                        await connection.close()

        return start_consuming_callable

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister a consumer.

        Not implemented for this integration, as once the connection/channel is
        closed, the consumer is deregistered.
        """
        pass

    async def cleanup(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        """Perform any clean up of queues and exchanges."""
        connection = await self.new_connection()
        async with connection:
            channel = await connection.channel()
            for queue_name in self._registered_topics:
                await channel.queue_delete(queue_name=queue_name)
            await channel.exchange_delete(exchange_name=self._config.exchange_name)

    def as_config(self) -> BaseModel:
        return RabbitMQMessageQueueConfig(
            url=self._config.url, exchange_name=self._config.exchange_name
        )
