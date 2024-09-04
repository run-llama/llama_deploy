"""RabbitMQ Message Queue."""

import asyncio
import json
from logging import getLogger
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from llama_deploy.message_queues.base import (
    BaseMessageQueue,
)
from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)

if TYPE_CHECKING:
    from aio_pika import Connection, Queue

logger = getLogger(__name__)


DEFAULT_URL = "amqp://guest:guest@localhost/"
DEFAULT_EXCHANGE_NAME = "llama-deploy"


class RabbitMQMessageQueueConfig(BaseSettings):
    """RabbitMQ message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="RABBITMQ_")

    url: str = DEFAULT_URL
    exchange_name: str = DEFAULT_EXCHANGE_NAME
    username: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    vhost: Optional[str] = None
    secure: Optional[bool] = None

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
    except ImportError:
        raise ValueError(
            "Missing pika optional dep. Please install by running `pip install llama-deploy[rabbimq]`."
        )
    return await aio_pika.connect(url)


class RabbitMQMessageQueue(BaseMessageQueue):
    """RabbitMQ integration with aio-pika client.

    This class creates a Work (or Task) Queue. For more information on Work Queues
    with RabbitMQ see the pages linked below:
        1. https://aio-pika.readthedocs.io/en/latest/rabbitmq-tutorial/2-work-queues.html
        2. https://aio-pika.readthedocs.io/en/latest/rabbitmq-tutorial/3-publish-subscribe.html

    Connections are established by url that use amqp uri scheme
    (https://www.rabbitmq.com/docs/uri-spec#the-amqp-uri-scheme)
        amqp_URI       = "amqp://" amqp_authority [ "/" vhost ] [ "?" query ]
        amqp_authority = [ amqp_userinfo "@" ] host [ ":" port ]
        amqp_userinfo  = username [ ":" password ]
        username       = *( unreserved / pct-encoded / sub-delims )
        password       = *( unreserved / pct-encoded / sub-delims )
        vhost          = segment

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

    url: str = DEFAULT_URL
    exchange_name: str = DEFAULT_EXCHANGE_NAME

    def __init__(
        self,
        url: str = DEFAULT_URL,
        exchange_name: str = DEFAULT_EXCHANGE_NAME,
        **kwargs: Any,
    ) -> None:
        super().__init__(url=url, exchange_name=exchange_name)

    @classmethod
    def from_url_params(
        cls,
        username: str,
        password: str,
        host: str,
        vhost: str = "",
        port: Optional[int] = None,
        secure: bool = False,
        exchange_name: str = DEFAULT_EXCHANGE_NAME,
    ) -> "RabbitMQMessageQueue":
        """Convenience constructor from url params.

        Args:
            username (str): username for the amqp authority
            password (str): password for the amqp authority
            host (str): host for rabbitmq server
            port (Optional[int], optional): port for rabbitmq server. Defaults to None.
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
        if secure:
            if port:
                url = f"amqps://{username}:{password}@{host}:{port}/{vhost}"
            else:
                url = f"amqps://{username}:{password}@{host}/{vhost}"
        return cls(url=url, exchange_name=exchange_name)

    async def new_connection(self) -> "Connection":
        """Returns a new connection to the RabbitMQ server."""
        return await _establish_connection(self.url)

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to the queue."""
        from aio_pika import DeliveryMode, ExchangeType, Message as AioPikaMessage

        message_type_str = message.type
        connection = await _establish_connection(self.url)

        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                self.exchange_name,
                ExchangeType.DIRECT,
            )
            message_body = json.dumps(message.model_dump()).encode("utf-8")

            aio_pika_message = AioPikaMessage(
                message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
            )
            # Sending the message
            await exchange.publish(aio_pika_message, routing_key=message_type_str)
            logger.info(f"published message {message.id_}")

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        from aio_pika import ExchangeType, Message as AioPikaMessage

        connection = await _establish_connection(self.url)
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                self.exchange_name,
                ExchangeType.DIRECT,
            )
            queue: Queue = await channel.declare_queue(name=consumer.message_type)
            await queue.bind(exchange)

        logger.info(
            f"Registered consumer {consumer.id_}: {consumer.message_type}",
        )

        async def start_consuming_callable() -> None:
            """StartConsumingCallable.

            Consumer of this queue, should call this in order to start consuming.
            """

            async def on_message(message: AioPikaMessage) -> None:
                async with message.process():
                    decoded_message = json.loads(message.body.decode("utf-8"))
                    queue_message = QueueMessage.model_validate(decoded_message)
                    await consumer.process_message(queue_message)

            connection = await _establish_connection(self.url)
            async with connection:
                channel = await connection.channel()
                exchange = await channel.declare_exchange(
                    self.exchange_name,
                    ExchangeType.DIRECT,
                )
                queue: Queue = await channel.declare_queue(name=consumer.message_type)
                await queue.bind(exchange)

                await queue.consume(on_message)

                await asyncio.Future()

        return start_consuming_callable

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister a consumer.

        Not implemented for this integration, as once the connection/channel is
        closed, the consumer is deregistered.
        """
        pass

    async def processing_loop(self) -> None:
        """A loop for getting messages from queues and sending to consumer.

        Not relevant for this class.
        """
        pass

    async def launch_local(self) -> asyncio.Task:
        """Launch the message queue locally, in-process.

        Launches a dummy task.
        """
        return asyncio.create_task(self.processing_loop())

    async def launch_server(self) -> None:
        """Launch the message queue server.

        Not relevant for this class. RabbitMQ server should already be launched.
        """
        pass

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        """Perform any clean up of queues and exchanges."""
        connection = await self.new_connection()
        async with connection:
            channel = await connection.channel()
            for message_type in message_types:
                await channel.queue_delete(queue_name=message_type)
            await channel.exchange_delete(exchange_name=self.exchange_name)

    def as_config(self) -> BaseModel:
        return RabbitMQMessageQueueConfig(
            url=self.url, exchange_name=self.exchange_name
        )
