"""AWS SNS and SQS Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, PrivateAttr, SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)

if TYPE_CHECKING:
    from aiobotocore.session import AioSession
    from botocore.config import Config

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

    aws_region: str
    aws_access_key_id: Optional[str] = Field(default=None, exclude=True)
    aws_secret_access_key: Optional[str] = Field(default=None, exclude=True)

    def model_post_init(self, __context: Any) -> None:
        if not self.aws_region:
            raise ValueError("AWS region must be provided.")

    def get_credentials(self) -> Dict[str, Optional[str]]:
        """Returns the AWS credentials, defaulting to environment-based credentials if not provided."""
        return {
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
        }


class AWSMessageQueue(BaseMessageQueue):
    """AWS SQS integration with aiobotocore client.

    This class creates and interacts with SNS topics and SQS queues. It includes methods
    for publishing messages to the queue and registering consumers to process messages.

    Attributes:
        aws_region (str): The AWS region where the SNS topics and SQS queues are located.
    """

    aws_region: str
    aws_access_key_id: Optional[SecretStr]
    aws_secret_access_key: Optional[SecretStr]
    topics: List["Topic"] = []
    queues: List["Queue"] = []
    subscriptions: List["Subscription"] = []

    _aio_session: Optional["AioSession"] = PrivateAttr(None)
    _retry_config: "Config" = PrivateAttr()

    def __init__(self, **kwargs: Any) -> None:
        """Initialize AWSMessageQueue with config."""
        super().__init__(**kwargs)
        self._aio_session = None

        # AWS retry configuration with exponential backoff
        self._retry_config = Config(retries={"max_attempts": 5, "mode": "adaptive"})

    def get_credentials(self) -> Dict[str, Optional[str]]:
        """Returns the AWS credentials, defaulting to environment-based credentials if not provided."""
        return {
            "aws_access_key_id": (
                self.aws_access_key_id.get_secret_value()
                if self.aws_access_key_id
                else ""
            ),
            "aws_secret_access_key": (
                self.aws_secret_access_key.get_secret_value()
                if self.aws_secret_access_key
                else ""
            ),
        }

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

    async def get_topic_by_name(self, topic_name: str) -> "Topic":
        """Get topic by name."""
        from botocore.exceptions import ClientError

        session = self._get_aio_session()
        credentials = self.get_credentials()

        async with session.create_client(
            "sns",
            region_name=self.aws_region,
            config=self._retry_config,
            **credentials,
        ) as client:
            try:
                # First, check if the topic exists
                response = await client.list_topics()
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

        session = self._get_aio_session()
        credentials = self.get_credentials()

        async with session.create_client(
            "sns",
            region_name=self.aws_region,
            config=self._retry_config,
            **credentials,
        ) as client:
            try:
                # First, check if the topic exists
                response = await client.list_topics()
                for topic in response.get("Topics", []):
                    if topic_name in topic["TopicArn"]:
                        logger.info(f"SNS topic {topic_name} already exists.")
                        return Topic(arn=topic["TopicArn"], name=topic_name)

                # If not found, create the topic
                response = await client.create_topic(
                    Name=f"{topic_name}.fifo", Attributes={"FifoTopic": "true"}
                )
            except ClientError:
                raise

        topic = Topic(arn=response["TopicArn"], name=topic_name)
        if topic.arn not in [t.arn for t in self.topics]:
            self.topics.append(topic)
        return topic

    async def _create_sqs_queue(self, queue_name: str) -> "Queue":
        """Create AWS SQS Fifo queue or return existing one."""
        from botocore.exceptions import ClientError

        session = self._get_aio_session()
        credentials = self.get_credentials()

        async with session.create_client(
            "sqs",
            region_name=self.aws_region,
            config=self._retry_config,
            **credentials,
        ) as client:
            try:
                # Check if queue exists
                response = await client.list_queues(QueueNamePrefix=queue_name)
                if response.get("QueueUrls"):
                    logger.info(f"SQS queue {queue_name} already exists.")
                    queue_url = response["QueueUrls"][0]
                else:
                    # If not, create the queue
                    response = await client.create_queue(
                        QueueName=f"{queue_name}.fifo", Attributes={"FifoQueue": "true"}
                    )
                    queue_url = response["QueueUrl"]

                # Get queue ARN
                response = await client.get_queue_attributes(
                    QueueUrl=queue_url, AttributeNames=["QueueArn"]
                )
                queue_arn = response["Attributes"]["QueueArn"]
            except ClientError:
                raise

        queue = Queue(arn=queue_arn, url=queue_url, name=queue_name)
        if queue.arn not in [q.arn for q in self.queues]:
            self.queues.append(queue)
        return queue

    async def _update_queue_policy(self, queue: "Queue", topic: "Topic") -> None:
        """Update SQS queue policy to allow SNS topic to send messages."""
        session = self._get_aio_session()
        credentials = self.get_credentials()

        async with session.create_client(
            "sqs",
            region_name=self.aws_region,
            config=self._retry_config,
            **credentials,
        ) as client:
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
            await client.set_queue_attributes(
                QueueUrl=queue.url, Attributes={"Policy": policy}
            )

    async def _subscribe_queue_to_topic(
        self, topic: "Topic", queue: "Queue"
    ) -> "Subscription":
        """Subscribe SQS queue to the SNS topic and apply the queue policy."""
        from botocore.exceptions import ClientError

        session = self._get_aio_session()
        credentials = self.get_credentials()

        async with session.create_client(
            "sns",
            region_name=self.aws_region,
            config=self._retry_config,
            **credentials,
        ) as client:
            try:
                response = await client.subscribe(
                    TopicArn=topic.arn, Protocol="sqs", Endpoint=queue.arn
                )
            except ClientError as e:
                logger.error(
                    f"Could not subscribe SQS queue {queue.name} to SNS topic {topic.name}: {e}"
                )
                raise
        subscription = Subscription(arn=response["SubscriptionArn"])
        if subscription.arn not in [s.arn for s in self.subscriptions]:
            self.subscriptions.append(subscription)

        # Update the SQS queue policy to allow SNS topic to send messages
        await self._update_queue_policy(queue, topic)

        return subscription

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to the SQS queue."""
        from botocore.exceptions import ClientError

        message_body = json.dumps(message.model_dump())
        topic = await self.get_topic_by_name(message.type)
        session = self._get_aio_session()
        credentials = self.get_credentials()

        try:
            async with session.create_client(
                "sns",
                region_name=self.aws_region,
                config=self._retry_config,
                **credentials,
            ) as client:
                response = await client.publish(
                    TopicArn=topic.arn,
                    Message=message_body,
                    MessageStructure="bytes",
                    MessageGroupId=message.id_,  # Assigning message id as the group id for simplicity
                    MessageDeduplicationId=message.id_,
                )
                logger.info(f"Published {message.type} message {message.id_}")
                return response
        except ClientError as e:
            logger.error(f"Could not publish message to SQS queue: {e}")
            raise

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        """Perform cleanup of queues and topics."""
        from botocore.exceptions import ClientError

        session = self._get_aio_session()
        credentials = self.get_credentials()

        async with session.create_client(
            "sqs",
            region_name=self.aws_region,
            config=self._retry_config,
            **credentials,
        ) as sqs_client, session.create_client(
            "sns",
            region_name=self.aws_region,
            config=self._retry_config,
            **credentials,
        ) as sns_client:
            # Delete all SQS queues
            for queue in self.queues:
                try:
                    await sqs_client.delete_queue(QueueUrl=queue.url)
                    logger.info(f"Deleted SQS queue {queue.name}")
                except ClientError as e:
                    logger.error(f"Could not delete SQS queue {queue.name}: {e}")

            # Delete all SNS topics
            for topic in self.topics:
                try:
                    await sns_client.delete_topic(TopicArn=topic.arn)
                    logger.info(f"Deleted SNS topic {topic.name}")
                except ClientError as e:
                    logger.error(f"Could not delete SNS topic {topic.name}: {e}")

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        from botocore.exceptions import ClientError

        topic = await self._create_sns_topic(topic_name=consumer.message_type)
        queue = await self._create_sqs_queue(queue_name=consumer.message_type)
        await self._subscribe_queue_to_topic(queue=queue, topic=topic)
        logger.info(f"Registered consumer {consumer.id_}: {consumer.message_type}")

        async def start_consuming_callable() -> None:
            """Start consuming messages."""
            while True:
                session = self._get_aio_session()
                credentials = self.get_credentials()

                async with session.create_client(
                    "sqs",
                    region_name=self.aws_region,
                    config=self._retry_config,
                    **credentials,
                ) as client:
                    try:
                        response = await client.receive_message(
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
                            await client.delete_message(
                                QueueUrl=queue.url, ReceiptHandle=receipt_handle
                            )
                    except ClientError as e:
                        logger.error(f"Error receiving messages from SQS queue: {e}")

        return start_consuming_callable

    def as_config(self) -> BaseModel:
        return AWSMessageQueueConfig(aws_region=self.aws_region)

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> Any:
        """Deregister a consumer.

        Not implemented for this integration, as SQS does not maintain persistent consumers.
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

        Not relevant for this class. AWS SQS server should already be available.
        """
        pass
