"""Apache Kafka Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import Any, Callable, Coroutine, Dict, List, Optional
from llama_agents import CallableMessageConsumer, QueueMessage
from llama_agents.message_queues.base import (
    BaseMessageQueue,
)
from llama_agents.message_consumers.base import (
    BaseMessageQueueConsumer,
)

import logging

logger = getLogger(__name__)
logger.setLevel(logging.INFO)


DEFAULT_URL = "localhost:9092"
DEFAULT_TOPIC_PARTITIONS = 10
DEFAULT_TOPIC_REPLICATION_FACTOR = 1
DEFAULT_GROUP_ID = "default_group"  # single group for competing consumers


class KafkaMessageQueue(BaseMessageQueue):
    """Apache Kafka integration with aiokafka."""

    url: str = DEFAULT_URL

    def __init__(
        self,
        url: str = DEFAULT_URL,
    ) -> None:
        super().__init__(url=url)

    @classmethod
    def from_url_params(
        cls,
        host: str,
        port: Optional[int] = None,
    ) -> "KafkaMessageQueue":
        url = f"{host}:{port}" if port else f"{host}"
        return cls(url=url)

    def _create_new_topic(
        self,
        topic_name: str,
        num_partitions: Optional[int] = None,
        replication_factor: Optional[int] = None,
        **kwargs: Dict[str, Any],
    ) -> None:
        """Create a new topic.

        Use kafka-python-ng instead of aio-kafka as latter has issues with
        resolving api_version with broker.

        TODO: convert to aiokafka once this it is resolved there.
        """
        from kafka.admin import KafkaAdminClient, NewTopic
        from kafka.errors import TopicAlreadyExistsError

        admin_client = KafkaAdminClient(bootstrap_servers=self.url)
        try:
            topic = NewTopic(
                name=topic_name,
                num_partitions=num_partitions or DEFAULT_TOPIC_PARTITIONS,
                replication_factor=replication_factor
                or DEFAULT_TOPIC_REPLICATION_FACTOR,
                **kwargs,
            )
            admin_client.create_topics(new_topics=[topic])
            logger.info(f"New topic {topic_name} created.")
        except TopicAlreadyExistsError:
            logger.info(f"Topic {topic_name} already exists.")
            pass

    async def _publish(self, message: QueueMessage) -> Any:
        ...

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        ...

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        ...

    async def launch_local(self) -> asyncio.Task:
        return asyncio.create_task(self.processing_loop())

    async def launch_server(self) -> None:
        ...

    async def processing_loop(self) -> None:
        pass

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        """Register a new consumer."""
        from aiokafka import AIOKafkaConsumer

        # register topic
        self._create_new_topic(consumer.message_type)

        async def start_consuming_callable() -> None:
            """StartConsumingCallable."""

            kafka_consumer = AIOKafkaConsumer(
                consumer.message_type,
                bootstrap_servers=self.url,
                group_id=DEFAULT_GROUP_ID,
            )
            await kafka_consumer.start()
            try:
                async for msg in kafka_consumer:
                    decoded_message = json.loads(msg.value.decode("utf-8"))
                    queue_message = QueueMessage.model_validate(decoded_message)
                    await consumer.process_message(queue_message)
            finally:
                await kafka_consumer.stop()

        return start_consuming_callable


async def main() -> None:
    mq = KafkaMessageQueue()
    mq._create_new_topic(topic_name="test")

    # register a sample consumer
    test_consumer = CallableMessageConsumer(
        message_type="test", handler=lambda msg: print(msg)
    )

    start_consuming_callable = await mq.register_consumer(test_consumer)
    task = asyncio.create_task(start_consuming_callable())

    task.cancel()


if __name__ == "__main__":
    import logging
    import logging
    import sys

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    logger.addHandler(logging.StreamHandler(stream=sys.stdout))
    asyncio.run(main())
