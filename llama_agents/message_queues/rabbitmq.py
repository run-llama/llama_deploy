"""RabbitMQ Message Queue."""

import asyncio
import json

from logging import getLogger
from typing import Any, Optional, TYPE_CHECKING

from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import BaseMessageQueueConsumer

if TYPE_CHECKING:
    from pika import BlockingConnection


logger = getLogger(__name__)


def _establish_connection(host: str, port: Optional[int]) -> "BlockingConnection":
    try:
        import pika
    except ImportError:
        raise ValueError(
            "Missing pika optional dep. Please install by running `pip install llama-agents[rabbimq]`."
        )
    return pika.BlockingConnection(pika.ConnectionParameters(host=host, port=port))


class RabbitMQMessageQueue(BaseMessageQueue):
    """RabbitMQ integration."""

    host: str = "localhost"
    port: Optional[int] = 5672

    @property
    def client(self) -> "BlockingConnection":
        return self._client

    async def _publish(self, message: QueueMessage) -> Any:
        message_type_str = message.type
        connection = _establish_connection(self.host, self.port)
        channel = connection.channel()
        channel.queue_declare(queue=message_type_str)
        channel.basic_publish(
            exchange="",
            routing_key=message_type_str,
            body=json.dumps(message.model_dump()),
        )
        connection.close()
        logger.info(f"published message {message.id_}")

    async def register_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        print(
            f"registering consumer {consumer.id_}: {consumer.message_type}", flush=True
        )
        connection = _establish_connection(self.host, self.port)
        channel = connection.channel()
        channel.queue_declare(queue=consumer.message_type)

        def callback(channel, method, properties, body):  # type: ignore
            print(f"Received message {body}", flush=True)
            json_str = str(body)
            message = QueueMessage.model_validate(json_str)
            return asyncio.run(consumer.process_message(message))

        channel.basic_consume(
            queue=consumer.message_type, auto_ack=True, on_message_callback=callback
        )
        print(
            f"FINISHED registering consumer {consumer.id_}: {consumer.message_type}",
            flush=True,
        )
        return channel

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        pass

    async def processing_loop(self) -> None:
        pass

    async def launch_local(self) -> asyncio.Task:
        raise NotImplementedError()

    async def launch_server(self) -> None:
        pass
