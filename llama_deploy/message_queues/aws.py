"""AWS SNS and SQS Message Queue."""

import json
from asyncio import CancelledError
from logging import getLogger
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_deploy.message_queues.base import AbstractMessageQueue
from llama_deploy.messages.base import QueueMessage

if TYPE_CHECKING:  # pragma: no cover
    from aiobotocore.session import AioSession, ClientCreatorContext

logger = getLogger(__name__)


class BaseAWSResource(BaseModel):
    arn: str


class Topic(BaseAWSResource):
    """Light data class for AWS SNS Topic."""

    name: str


class Queue(BaseAWSResource):
    """Light data class for AWS SQS Queue."""

    url: str
    name: str


class Subscription(BaseAWSResource):
    """Light data class for AWS SNS Subscription."""


class AWSMessageQueueConfig(BaseSettings):
    """AWS SNS and SQS message queue configuration."""

    model_config = SettingsConfigDict()

    type: Literal["aws"] = Field(default="aws", exclude=True)
    aws_region: str = "us-east-1"
    aws_access_key_id: SecretStr | None = Field(default=None, exclude=True)
    aws_secret_access_key: SecretStr | None = Field(default=None, exclude=True)


class AWSMessageQueue(AbstractMessageQueue):
    """AWS SQS integration with aiobotocore client.

    This class creates and interacts with SNS topics and SQS queues. It includes methods
    for publishing messages to the queue and registering consumers to process messages.

    Authentication:
    The class attempts authentication methods in the following order:
    1. IAM Role: Automatically used when deployed on AWS infrastructure (EC2, ECS, etc.).
    2. Environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (fallback).

    Region selection:
    - aws_region must be provided.

    IAM Roles are strongly recommended for production deployments on AWS infrastructure (EC2, ECS).
    For local development, environment variables can be used. Explicit credentials should be avoided
    in production due to security risks.

    Attributes:
        aws_region (str): The AWS region for SNS topics and SQS queues.
        aws_access_key_id (Optional[SecretStr]): AWS access key ID (fallback to environment variables).
        aws_secret_access_key (Optional[SecretStr]): AWS secret access key (fallback to environment variables).
    """

    def __init__(self, config: AWSMessageQueueConfig | None = None) -> None:
        """Initialize AWSMessageQueue with config."""
        try:
            from botocore.config import Config
        except ImportError:
            raise ValueError(
                "Missing `botocore` package. Please install by running `pip install llama-deploy[aws]`."
            )
        self._config = config or AWSMessageQueueConfig()
        self._topics: list["Topic"] = []
        self._queues: list["Queue"] = []
        self._subscriptions: list["Subscription"] = []
        self._aio_session: "AioSession | None" = None
        # AWS retry configuration with exponential backoff
        self._retry_config = Config(retries={"max_attempts": 5, "mode": "adaptive"})
        if not self._config.aws_access_key_id or not self._config.aws_secret_access_key:
            logger.info(
                "Using default AWS credential provider chain (IAM Role or environment variables)."
            )

    def _get_aio_session(self) -> "AioSession":
        if self._aio_session is None:
            try:
                from aiobotocore.session import get_session
            except ImportError:
                raise ValueError(
                    "Missing `aiobotocore`. Please install by running `pip install llama-deploy[aws]`."
                )
            self._aio_session = get_session()
        return self._aio_session

    def _get_client(self, service_name: str) -> "ClientCreatorContext":
        """Returns a client context manager."""
        session = self._get_aio_session()
        client_kwargs = {
            "region_name": self._config.aws_region,
            "config": self._retry_config,
            "service_name": service_name,
        }

        # IAM Role or environment variable fallback
        if self._config.aws_access_key_id and self._config.aws_secret_access_key:
            client_kwargs.update(
                {
                    "aws_access_key_id": self._config.aws_access_key_id.get_secret_value(),
                    "aws_secret_access_key": self._config.aws_secret_access_key.get_secret_value(),
                }
            )

        return session.create_client(**client_kwargs)  # type: ignore

    async def get_topic_by_name(self, topic_name: str) -> "Topic":
        """Get topic by name."""
        from botocore.exceptions import ClientError

        async with self._get_client("sns") as client:
            try:
                # First, check if the topic exists
                response = await client.list_topics()  # type: ignore
                print(response)
                for topic in response.get("Topics", []):
                    if f"{topic_name}.fifo" in topic["TopicArn"]:
                        logger.info(f"SNS topic {topic_name} already exists.")
                        return Topic(arn=topic["TopicArn"], name=topic_name)

                # didn't find topic
                raise ValueError(f"Could not find topic {topic_name}.")
            except ClientError:
                raise

    async def _create_sns_topic(self, topic_name: str) -> "Topic":
        """Create AWS SNS topic or return existing one."""
        from botocore.exceptions import ClientError

        async with self._get_client("sns") as client:
            try:
                # First, check if the topic exists
                response = await client.list_topics()  # type: ignore
                for topic in response.get("Topics", []):
                    if topic_name in topic["TopicArn"]:
                        logger.info(f"SNS topic {topic_name} already exists.")
                        return Topic(arn=topic["TopicArn"], name=topic_name)

                # If not found, create the topic
                response = await client.create_topic(  # type: ignore
                    Name=f"{topic_name}.fifo", Attributes={"FifoTopic": "true"}
                )
            except ClientError:
                raise

        topic = Topic(arn=response["TopicArn"], name=topic_name)
        if topic.arn not in [t.arn for t in self._topics]:
            self._topics.append(topic)
        return topic

    async def _create_sqs_queue(self, queue_name: str) -> "Queue":
        """Create AWS SQS Fifo queue or return existing one."""
        from botocore.exceptions import ClientError

        async with self._get_client("sqs") as client:
            try:
                # Check if queue exists
                response = await client.list_queues(QueueNamePrefix=queue_name)  # type: ignore
                if response.get("QueueUrls"):
                    logger.info(f"SQS queue {queue_name} already exists.")
                    queue_url = response["QueueUrls"][0]
                else:
                    # If not, create the queue
                    response = await client.create_queue(  # type: ignore
                        QueueName=f"{queue_name}.fifo", Attributes={"FifoQueue": "true"}
                    )
                    queue_url = response["QueueUrl"]

                # Get queue ARN
                response = await client.get_queue_attributes(  # type: ignore
                    QueueUrl=queue_url, AttributeNames=["QueueArn"]
                )
                queue_arn = response["Attributes"]["QueueArn"]
            except ClientError:
                raise

        queue = Queue(arn=queue_arn, url=queue_url, name=queue_name)
        if queue.arn not in [q.arn for q in self._queues]:
            self._queues.append(queue)
        return queue

    async def _update_queue_policy(self, queue: "Queue", topic: "Topic") -> None:
        """Update SQS queue policy to allow SNS topic to send messages."""
        async with self._get_client("sqs") as client:
            policy = json.dumps(
                {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": "SQS:SendMessage",
                            "Resource": queue.arn,
                            "Condition": {"ArnLike": {"aws:SourceArn": topic.arn}},
                        }
                    ],
                }
            )
            await client.set_queue_attributes(  # type: ignore
                QueueUrl=queue.url, Attributes={"Policy": policy}
            )

    async def _subscribe_queue_to_topic(
        self, topic: "Topic", queue: "Queue"
    ) -> "Subscription":
        """Subscribe SQS queue to the SNS topic and apply the queue policy."""
        from botocore.exceptions import ClientError

        async with self._get_client("sns") as client:
            try:
                response = await client.subscribe(  # type: ignore
                    TopicArn=topic.arn, Protocol="sqs", Endpoint=queue.arn
                )
            except ClientError as e:
                logger.error(
                    f"Could not subscribe SQS queue {queue.name} to SNS topic {topic.name}: {e}"
                )
                raise
        subscription = Subscription(arn=response["SubscriptionArn"])
        if subscription.arn not in [s.arn for s in self._subscriptions]:
            self._subscriptions.append(subscription)

        # Update the SQS queue policy to allow SNS topic to send messages
        await self._update_queue_policy(queue, topic)

        return subscription

    async def _publish(self, message: QueueMessage, topic: str) -> Any:
        """Publish message to the SQS queue."""
        from botocore.exceptions import ClientError

        message_body = json.dumps(message.model_dump())
        _topic = await self.get_topic_by_name(topic)

        try:
            async with self._get_client("sns") as client:
                response = await client.publish(  # type: ignore
                    TopicArn=_topic.arn,
                    Message=message_body,
                    MessageStructure="bytes",
                    MessageGroupId=message.id_,  # Assigning message id as the group id for simplicity
                    MessageDeduplicationId=message.id_,
                )
                logger.info(
                    f"Published message {message.id_} of type {message.type} on topic {topic}"
                )
                return response
        except ClientError as e:
            logger.error(f"Could not publish message to SQS queue: {e}")
            raise

    async def cleanup(self, *args: Any, **kwargs: dict[str, Any]) -> None:
        """Perform cleanup of queues and topics."""
        from botocore.exceptions import ClientError

        async with (
            self._get_client("sqs") as sqs_client,
            self._get_client("sns") as sns_client,
        ):
            # Delete all SQS queues
            for queue in self._queues:
                try:
                    await sqs_client.delete_queue(QueueUrl=queue.url)  # type: ignore
                    logger.info(f"Deleted SQS queue {queue.name}")
                except ClientError as e:
                    logger.error(f"Could not delete SQS queue {queue.name}: {e}")

            # Delete all SNS topics
            for topic in self._topics:
                try:
                    await sns_client.delete_topic(TopicArn=topic.arn)  # type: ignore
                    logger.info(f"Deleted SNS topic {topic.name}")
                except ClientError as e:
                    logger.error(f"Could not delete SNS topic {topic.name}: {e}")

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, topic: str
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        from botocore.exceptions import ClientError

        _topic = await self._create_sns_topic(topic_name=topic)
        queue = await self._create_sqs_queue(queue_name=topic)
        await self._subscribe_queue_to_topic(queue=queue, topic=_topic)
        logger.info(f"Registered consumer {consumer.id_} for topic {topic}")

        async def start_consuming_callable() -> None:
            """Start consuming messages."""
            while True:
                try:
                    async with self._get_client("sqs") as client:
                        try:
                            response = await client.receive_message(  # type: ignore
                                QueueUrl=queue.url,
                                WaitTimeSeconds=2,
                            )
                            messages = response.get("Messages", [])
                            for msg in messages:
                                receipt_handle = msg["ReceiptHandle"]
                                message_body = json.loads(msg["Body"])
                                queue_message_data = json.loads(message_body["Message"])
                                queue_message = QueueMessage.model_validate(
                                    queue_message_data
                                )
                                await consumer.process_message(queue_message)
                                await client.delete_message(  # type: ignore
                                    QueueUrl=queue.url, ReceiptHandle=receipt_handle
                                )
                        except ClientError as e:
                            logger.error(
                                f"Error receiving messages from SQS queue: {e}"
                            )
                except CancelledError:
                    return

        return start_consuming_callable

    def as_config(self) -> BaseModel:
        """Return the current configuration as an AWSMessageQueueConfig object."""
        return self._config

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister a consumer.

        Not implemented for this integration, as SQS does not maintain persistent consumers.
        """
        pass
