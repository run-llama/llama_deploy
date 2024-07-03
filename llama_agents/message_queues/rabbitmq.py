"""RabbitMQ Message Queue."""

import asyncio
import json
import nest_asyncio
from logging import getLogger
from pydantic import PrivateAttr
from typing import Any, Optional, TYPE_CHECKING
from llama_agents.message_queues.base import (
    BaseMessageQueue,
    BaseChannel,
    AsyncProcessMessageCallable,
)
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import BaseMessageQueueConsumer

if TYPE_CHECKING:
    from pika.adapters.blocking_connection import BlockingConnection, BlockingChannel

nest_asyncio.apply()
logger = getLogger(__name__)


class RabbitMQChannel(BaseChannel):
    _pika_channel: "BlockingChannel" = PrivateAttr()
    _pika_connection: "BlockingConnection" = PrivateAttr()

    def __init__(
        self, pika_channel: "BlockingChannel", pika_connection: "BlockingConnection"
    ) -> None:
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


def _establish_connection(host: str, port: Optional[int]) -> "BlockingConnection":
    try:
        import pika
    except ImportError:
        raise ValueError(
            "Missing pika optional dep. Please install by running `pip install llama-agents[rabbimq]`."
        )
    return pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port))


class RabbitMQMessageQueue(BaseMessageQueue):
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
    exchange: str = "llama-agents"

    def __init__(
        self,
        host: str = "localhost",
        port: Optional[int] = 5672,
        exchange: str = "llama-agents",
    ) -> None:
        super().__init__(host=host, port=port, exchange=exchange)
        connection = _establish_connection(self.host, self.port)
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange, exchange_type="direct")

    def new_connection(self) -> "BlockingConnection":
        return _establish_connection(self.host, self.port)

    async def _publish(self, message: QueueMessage) -> Any:
        message_type_str = message.type
        connection = _establish_connection(self.host, self.port)
        channel = connection.channel()
        channel.queue_declare(queue=message_type_str)
        channel.basic_publish(
            exchange=self.exchange,
            routing_key=message_type_str,
            body=json.dumps(message.model_dump()),
        )
        connection.close()
        logger.info(f"published message {message.id_}")

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer
    ) -> RabbitMQChannel:
        connection = _establish_connection(self.host, self.port)
        channel = connection.channel()
        channel.queue_declare(queue=consumer.message_type)
        channel.queue_bind(exchange=self.exchange, queue=consumer.message_type)

        logger.info(
            f"Registered consumer {consumer.id_}: {consumer.message_type}",
        )
        return RabbitMQChannel(channel, connection)

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        pass

    async def processing_loop(self) -> None:
        pass

    async def launch_local(self) -> Optional[asyncio.Task]:
        pass

    async def launch_server(self) -> None:
        pass
