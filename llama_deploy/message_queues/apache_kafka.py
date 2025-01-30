"""Apache Kafka Message Queue."""

import asyncio
import json
import logging
from logging import getLogger
from typing import Any, Dict, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.messages.base import QueueMessage

logger = getLogger(__name__)
logger.setLevel(logging.INFO)


DEFAULT_URL = "localhost:9092"
DEFAULT_TOPIC_PARTITIONS = 10
DEFAULT_TOPIC_REPLICATION_FACTOR = 1
DEFAULT_TOPIC_NAME = "control_plane"
DEFAULT_GROUP_ID = "default_group"  # single group for competing consumers


class KafkaMessageQueueConfig(BaseSettings):
    """Kafka message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="KAFKA_")

    type: Literal["kafka"] = Field(default="kafka", exclude=True)
    url: str = DEFAULT_URL
    host: str | None = None
    port: int | None = None

    @model_validator(mode="after")
    def update_url(self) -> "KafkaMessageQueueConfig":
        if self.host and self.port:
            self.url = f"{self.host}:{self.port}"
        return self


class KafkaMessageQueue(AbstractMessageQueue):
    """Apache Kafka integration with aiokafka.

    This class implements a traditional message broker using Apache Kafka.
        - Topics are created with N partitions
        - Consumers are registered to a single group to implement a competing
        consumer scheme where only one consumer subscribed to a topic gets the
        message
            - Default round-robin assignment is used

    Attributes:
        url (str): The broker url string to connect to the Kafka server

    Examples:
        ```python
        from llama_deploy.message_queues.apache_kafka import KafkaMessageQueue

        message_queue = KafkaMessageQueue()  # uses the default url
        ```
    """

    def __init__(self, config: KafkaMessageQueueConfig | None = None) -> None:
        self._config = config or KafkaMessageQueueConfig()
        self._kafka_consumers: dict[str, Any] = {}
        self._registered_topics: set[str] = set()

    @classmethod
    def from_url_params(
        cls,
        host: str,
        port: int | None = None,
    ) -> "KafkaMessageQueue":
        """Convenience constructor from url params.

        Args:
            host (str): host for rabbitmq server
            port (Optional[int], optional): port for rabbitmq server. Defaults to None.

        Returns:
            KafkaMessageQueue: An Apache Kafka MessageQueue integration.
        """
        url = f"{host}:{port}" if port else f"{host}"
        return cls(KafkaMessageQueueConfig(url=url))

    def _create_new_topic(
        self,
        topic_name: str,
        num_partitions: int | None = None,
        replication_factor: int | None = None,
        **kwargs: Dict[str, Any],
    ) -> None:
        """Create a new topic.

        Use kafka-python-ng instead of aio-kafka as latter has issues with
        resolving api_version with broker.

        TODO: convert to aiokafka once this it is resolved there.
        """
        try:
            from kafka.admin import KafkaAdminClient, NewTopic
            from kafka.errors import TopicAlreadyExistsError
        except ImportError:
            raise ImportError(
                "kafka-python-ng is not installed. "
                "Please install it using `pip install kafka-python-ng`."
            )

        admin_client = KafkaAdminClient(bootstrap_servers=self._config.url)
        try:
            topic = NewTopic(
                name=topic_name,
                num_partitions=num_partitions or DEFAULT_TOPIC_PARTITIONS,
                replication_factor=replication_factor
                or DEFAULT_TOPIC_REPLICATION_FACTOR,
                **kwargs,
            )
            admin_client.create_topics(new_topics=[topic])
            self._registered_topics.add(topic_name)
            logger.info(f"New topic {topic_name} created.")
        except TopicAlreadyExistsError:
            logger.info(f"Topic {topic_name} already exists.")
            pass

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        """Publish message to the queue."""
        try:
            from aiokafka import AIOKafkaProducer
        except ImportError:
            raise ImportError(
                "aiokafka is not installed. "
                "Please install it using `pip install aiokafka`."
            )

        producer = AIOKafkaProducer(bootstrap_servers=self._config.url)
        await producer.start()
        try:
            message_body = json.dumps(message.model_dump()).encode("utf-8")
            await producer.send_and_wait(topic, message_body)
            logger.info(f"published message {message.id_}")
        finally:
            await producer.stop()

    async def cleanup(self, *args: Any, **kwargs: Dict[str, Any]) -> None:
        """Cleanup for local runs.

        Use kafka-python-ng instead of aio-kafka as latter has issues with
        resolving api_version with broker when using admin client.

        TODO: convert to aiokafka once this it is resolved there.
        """
        try:
            from kafka.admin import KafkaAdminClient
        except ImportError:
            raise ImportError(
                "aiokafka is not installed. "
                "Please install it using `pip install aiokafka`."
            )

        admin_client = KafkaAdminClient(bootstrap_servers=self._config.url)
        active_topics = admin_client.list_topics()
        topics_to_delete = [el for el in self._registered_topics if el in active_topics]
        admin_client.delete_consumer_groups(DEFAULT_GROUP_ID)
        if topics_to_delete:
            admin_client.delete_topics(topics_to_delete)

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister a consumer."""
        if consumer.id_ in self._kafka_consumers:
            await self._kafka_consumers[consumer.id_].stop()

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, topic: str
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError:
            raise ImportError(
                "aiokafka is not installed. "
                "Please install it using `pip install aiokafka`."
            )

        if consumer.id_ in self._kafka_consumers:
            msg = f"Consumer {consumer.id_} already registered for topic {topic}"
            raise ValueError(msg)

        self._create_new_topic(topic)
        kafka_consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=self._config.url,
            group_id=DEFAULT_GROUP_ID,
            auto_offset_reset="earliest",
        )
        self._kafka_consumers[consumer.id_] = kafka_consumer

        await kafka_consumer.start()

        logger.info(
            f"Registered consumer {consumer.id_} for message type '{consumer.message_type}' on topic '{topic}'",
        )

        async def start_consuming_callable() -> None:
            """StartConsumingCallable."""
            try:
                async for msg in kafka_consumer:
                    if msg.value is None:
                        raise RuntimeError("msg.value is None")
                    decoded_message = json.loads(msg.value.decode("utf-8"))
                    queue_message = QueueMessage.model_validate(decoded_message)
                    await consumer.process_message(queue_message)
            finally:
                stop_task = asyncio.create_task(kafka_consumer.stop())
                stop_task.add_done_callback(
                    lambda _: logger.info(
                        f"stopped kafka consumer {consumer.id_}: {consumer.message_type} on topic {topic}"
                    )
                )
                await asyncio.shield(stop_task)
                del self._kafka_consumers[consumer.id_]

        return start_consuming_callable

    def as_config(self) -> BaseModel:
        return self._config
