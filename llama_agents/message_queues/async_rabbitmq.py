"""RabbitMQ Message Queue."""

import asyncio
import json
from logging import getLogger
from pydantic import PrivateAttr
from typing import Any, Optional, Callable, TYPE_CHECKING
from llama_agents.message_queues.base import (
    BaseMessageQueue,
)
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)

if TYPE_CHECKING:
    from aio_pika import Connection, Channel, Exchange, ExchangeType, Queue

logger = getLogger(__name__)


async def _establish_connection(url: str):
    try:
        import aio_pika
    except ImportError:
        raise ValueError(
            "Missing pika optional dep. Please install by running `pip install llama-agents[rabbimq]`."
        )
    return await aio_pika.connect(url)


class AsyncRabbitMQMessageQueue(BaseMessageQueue):
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
    """

    url: str = "amqp://guest:guest@localhost/"
    exchange_name: str = "llama-agents"

    def __init__(
        self,
        url: str = "amqp://guest:guest@localhost/",
        exchange_name: str = "llama-agents",
    ) -> None:
        super().__init__(url=url, exchange_name=exchange_name)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_url_params(
        cls,
        username=str,
        password=str,
        host=str,
        port: Optional[int] = None,
        secure: bool = False,
        exchange_name: str = "llama-agents",
    ) -> "AsyncRabbitMQMessageQueue":
        if not secure:
            if port:
                url = f"amqp://{username}:{password}@{host}:{port}/vhost"
            else:
                url = f"amqp://{username}:{password}@{host}/vhost"
        if secure:
            if port:
                url = f"amqps://{username}:{password}@{host}:{port}/vhost"
            else:
                url = f"amqps://{username}:{password}@{host}/vhost"
        return cls(url=url, exchange_name=exchange_name)

    async def new_connection(self) -> "Connection":
        return await _establish_connection(self.url)

    async def _publish(self, message: QueueMessage) -> Any:
        from aio_pika import DeliveryMode, ExchangeType, Message

        message_type_str = message.type
        connection = await _establish_connection(self.url)

        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                self.exchange_name,
                ExchangeType.DIRECT,
            )
            message_body = json.dumps(message.model_dump()).encode("utf-8")

            pika_message = Message(
                message_body,
                delivery_mode=DeliveryMode.PERSISTENT,
            )
            # Sending the message
            await exchange.publish(pika_message, routing_key=message_type_str)
            logger.info(f"published message {message.id_}")

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer
    ) -> Optional[StartConsumingCallable]:
        from aio_pika import DeliveryMode, ExchangeType, Message

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

        async def start_consuming():
            async def on_message(message) -> None:
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

        return start_consuming

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        pass

    async def processing_loop(self) -> None:
        pass

    async def launch_local(self) -> Optional[asyncio.Task]:
        pass

    async def launch_server(self) -> None:
        pass
