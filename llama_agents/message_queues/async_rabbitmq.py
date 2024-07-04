"""RabbitMQ Message Queue."""

import asyncio
import json
from logging import getLogger
from pydantic import PrivateAttr
from typing import Any, Optional, Callable, TYPE_CHECKING
from llama_agents.message_queues.base import (
    BaseMessageQueue,
    BaseChannel,
    AsyncProcessMessageCallable,
)
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import BaseMessageQueueConsumer

if TYPE_CHECKING:
    from aio_pika import Connection, Channel, Exchange, ExchangeType, Queue

logger = getLogger(__name__)


class AsyncRabbitMQChannel(BaseChannel):
    _pika_channel: "Channel" = PrivateAttr()

    def __init__(self, pika_channel: "Channel", pika_connection: "Connection") -> None:
        super().__init__()
        self._pika_channel = pika_channel
        self._pika_connection = pika_connection

    async def start_consuming(
        self, process_message: AsyncProcessMessageCallable, message_type: str
    ) -> Any:
        for message in self._pika_channel.consume(message_type, inactivity_timeout=1):
            if not all(message):
                continue
            _methods, _properties, body = message
            payload = json.loads(body.decode("utf-8"))
            message = QueueMessage.model_validate(payload)
            await process_message(message)

    async def stop_consuming(self) -> None:
        self._pika_channel.cancel()


async def _establish_connection(host: str, port: Optional[int]):
    try:
        import aio_pika
    except ImportError:
        raise ValueError(
            "Missing pika optional dep. Please install by running `pip install llama-agents[rabbimq]`."
        )
    return await aio_pika.connect("amqp://guest:guest@localhost/")


class AsyncRabbitMQMessageQueue(BaseMessageQueue):
    """RabbitMQ integration.

    This class creates a Work (or Task) Queue. For more information on Work Queues
    with RabbitMQ see the pages linked below:
        1. https://www.rabbitmq.com/tutorials/tutorial-two-python.
        2. https://www.rabbitmq.com/tutorials/amqp-concepts#:~:text=The%20default%20exchange%20is%20a,same%20as%20the%20queue%20name.

    The Work Queue created has the following properties:
        - Exchange with name self.exchange
        - Messages are published to this queue through the exchange
        - Consumers are bound to the exchange and have queues based on their
            message type
        - Round-robin dispatching: with multiple consumers listening to the same
            queue, only one consumer will be chosen dictated by sequence.
    """

    host: str = "localhost"
    port: Optional[int] = 5672
    exchange_name: str = "llama-agents"

    def __init__(
        self,
        host: str = "localhost",
        port: Optional[int] = 5672,
        exchange_name: str = "llama-agents",
    ) -> None:
        super().__init__(host=host, port=port, exchange_name=exchange_name)

    class Config:
        arbitrary_types_allowed = True

    async def new_connection(self) -> "Connection":
        return await _establish_connection(self.host, self.port)

    async def _publish(self, message: QueueMessage) -> Any:
        from aio_pika import DeliveryMode, ExchangeType, Message

        message_type_str = message.type
        connection = await _establish_connection(self.host, self.port)

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
    ) -> Optional[Callable]:
        from aio_pika import DeliveryMode, ExchangeType, Message

        connection = await _establish_connection(self.host, self.port)
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

            connection = await _establish_connection(self.host, self.port)
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
