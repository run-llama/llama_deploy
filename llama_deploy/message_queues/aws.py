"""AWS SNS and SQS Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from botocore.exceptions import ClientError
from botocore.config import Config
from pydantic import BaseModel, PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)

if TYPE_CHECKING:
    from aiobotocore.session import AioSession

logger = getLogger(__name__)

# AWS retry configuration with exponential backoff
RETRY_CONFIG = Config(
    retries={
        "max_attempts": 5,
        "mode": "adaptive"
    }
)

class AWSMessageQueueConfig(BaseSettings):
    """AWS SNS and SQS message queue configuration."""
    
    model_config = SettingsConfigDict(env_prefix="AWS_")

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str

    def model_post_init(self, __context: Any) -> None:
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            raise ValueError("AWS credentials (access key and secret key) must be provided.")


class AWSMessageQueue(BaseMessageQueue):
    """AWS SQS integration with aiobotocore client.

    This class creates and interacts with SNS topics and SQS queues. It includes methods 
    for publishing messages to the queue and registering consumers to process messages.

    Attributes:
        aws_region (str): The AWS region where the SNS topics and SQS queues are located.
    """

    config: AWSMessageQueueConfig
    topics: List["Topic"] = []
    queues: List["Queue"] = []
    subscriptions: List["Subscription"] = []
    _aio_session: Optional["AioSession"] = PrivateAttr(None)

    def __init__(self, config: AWSMessageQueueConfig) -> None:
        """Initialize AWSMessageQueue with config."""
        super().__init__()
        self.config = config
        self._aio_session = None

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

    def get_topic_by_name(self, topic_name: str) -> "Topic":
        """Get topic by name."""
        try:
            topic = next(t for t in self.topics if t.name == topic_name)
        except StopIteration:
            raise ValueError(f"Could not find topic {topic_name}.")
        return topic

    async def _create_sns_topic(self, topic_name: str) -> "Topic":
        """Create AWS SNS topic or return existing one."""
        session = self._get_aio_session()
        async with session.create_client(
            "sns", 
            region_name=self.config.aws_region, 
            config=RETRY_CONFIG, 
            aws_access_key_id=self.config.aws_access_key_id,
            aws_secret_access_key=self.config.aws_secret_access_key
        ) as client:
            try:
                response = await client.create_topic(
                    Name=f"{topic_name}.fifo", Attributes={"FifoTopic": "true"}
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceInUseException":
                    logger.info(f"SNS topic {topic_name} already exists.")
                    response = await client.get_topic_attributes(
                        TopicArn=f"arn:aws:sns:{self.config.aws_region}:{topic_name}.fifo"
                    )
                else:
                    raise
        topic = Topic(arn=response["TopicArn"], name=topic_name)
        if topic.arn not in [t.arn for t in self.topics]:
            self.topics.append(topic)
        return topic

    async def _create_sqs_queue(self, queue_name: str) -> "Queue":
        """Create AWS SQS Fifo queue or return existing one."""
        session = self._get_aio_session()
        async with session.create_client(
            "sqs", 
            region_name=self.config.aws_region, 
            config=RETRY_CONFIG,
            aws_access_key_id=self.config.aws_access_key_id,
            aws_secret_access_key=self.config.aws_secret_access_key
        ) as client:
            try:
                response = await client.create_queue(
                    QueueName=f"{queue_name}.fifo", Attributes={"FifoQueue": "true"}
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "QueueAlreadyExists":
                    logger.info(f"SQS queue {queue_name} already exists.")
                    response = await client.get_queue_url(QueueName=f"{queue_name}.fifo")
                else:
                    raise

            queue_url = response["QueueUrl"]
            response = await client.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["QueueArn"]
            )
            queue_arn = response["Attributes"]["QueueArn"]
            queue = Queue(arn=queue_arn, url=queue_url, name=queue_name)
            if queue.arn not in [q.arn for q in self.queues]:
                self.queues.append(queue)
            return queue

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to the SQS queue."""
        message_body = json.dumps(message.model_dump())
        topic = self.get_topic_by_name(message.type)
        session = self._get_aio_session()
        try:
            async with session.create_client(
                "sns", 
                region_name=self.config.aws_region, 
                config=RETRY_CONFIG,
                aws_access_key_id=self.config.aws_access_key_id,
                aws_secret_access_key=self.config.aws_secret_access_key
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

    def as_config(self) -> BaseModel:
        return self.config
