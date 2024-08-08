"""AWS SQS Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import Any, Dict, List, TYPE_CHECKING
from botocore.exceptions import ClientError

from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)
from llama_agents.message_queues.aws_sqs.policies import (
    get_attributes_with_topic_policy,
)
from llama_agents.message_queues.aws_sqs.types import Topic, Queue, Subscription

if TYPE_CHECKING:
    from aiobotocore.session import AioSession

logger = getLogger(__name__)

DEFAULT_REGION = "us-east-1"
DEFAULT_MESSAGE_GROUP_ID = "llama-agents"

logger = getLogger(__name__)


class AWSMessageQueue(BaseMessageQueue):
    """AWS SQS integration with aiobotocore client.

    This class creates and interacts with SNS topics and SQS queues. It includes methods 
    for publishing messages to the queue and registering consumers to process messages.

    Attributes:
        region (str): The AWS region where the SQS queue is located.
        message_group_id (str): Name of the unique FIFO queue's MessageGroupId. Messages within the same group are processed sequentially, while messages in different groups can be processed concurrently.
    """

    region: str = DEFAULT_REGION
    message_group_id: str = DEFAULT_MESSAGE_GROUP_ID
    topics: List[Topic] = []
    queues: List[Queue] = []
    subscriptions: List[Subscription] = []

    def _get_aio_session(self) -> "AioSession":
        try:
            from aiobotocore.session import get_session
        except ImportError:
            raise ValueError(
                "Missing `aiobotocore`. Please install by running `pip install aiobotocore`."
            )

        return get_session()

    def get_topic_by_name(self, topic_name: str) -> Topic:
        """Get topic by name."""
        try:
            topic = next(t for t in self.topics if t.name == topic_name)
        except StopIteration:
            raise ValueError("Could not find topic arn.")
        return topic

    async def _create_sns_topic(self, topic_name: str) -> Topic:
        """Create AWS SNS topic."""
        session = self._get_aio_session()
        async with session.create_client("sns", region_name=self.region) as client:
            response = await client.create_topic(
                Name=f"{topic_name}.fifo", Attributes={"FifoTopic": "true"}
            )
        topic = Topic(arn=response["TopicArn"], name=topic_name)
        if topic.arn not in [t.arn for t in self.topics]:
            self.topics.append(topic)
        return topic

    async def _create_sqs_queue(self, queue_name: str) -> Queue:
        """Create AWS SQS Fifo queue."""
        session = self._get_aio_session()
        async with session.create_client("sqs", region_name=self.region) as client:
            # create queue
            response = await client.create_queue(
                QueueName=f"{queue_name}.fifo", Attributes={"FifoQueue": "true"}
            )
            queue_url = response["QueueUrl"]

            # get queue arn
            response = await client.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["QueueArn"]
            )
            queue_arn = response["Attributes"]["QueueArn"]
            queue = Queue(arn=queue_arn, url=queue_url, name=queue_name)
            if queue.arn not in [q.arn for q in self.queues]:
                self.queues.append(queue)
            return queue

    async def _update_queue_policy(self, queue: Queue, topic: Topic) -> None:
        session = self._get_aio_session()
        async with session.create_client("sqs", region_name=self.region) as client:
            attributes = get_attributes_with_topic_policy(
                queue_arn=queue.arn, topic_arn=topic.arn
            )
            _ = await client.set_queue_attributes(
                QueueUrl=queue.url, Attributes=attributes
            )

    async def _subscribe_queue_to_topic(
        self, topic: Topic, queue: Queue
    ) -> Subscription:
        """Subscribe queue to topic."""
        session = self._get_aio_session()
        async with session.create_client("sns", region_name=self.region) as client:
            response = await client.subscribe(
                TopicArn=topic.arn, Protocol="sqs", Endpoint=queue.arn
            )
        subscription = Subscription(arn=response["SubscriptionArn"])
        if subscription.arn not in [s.arn for s in self.subscriptions]:
            self.subscriptions.append(subscription)
        return subscription

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to the SQS queue."""
        message_body = json.dumps(message.model_dump())
        topic = self.get_topic_by_name(message.type)
        session = self._get_aio_session()
        try:
            async with session.create_client("sns", region_name=self.region) as client:
                response = await client.publish(
                    TopicArn=topic.arn,
                    Message=message_body,
                    MessageStructure="bytes",
                    MessageGroupId=self.message_group_id,
                    MessageDeduplicationId=message.id_,
                )
                logger.info(f"Published {message.type} message {message.id_}")
                return response
        except ClientError as e:
            logger.error(f"Could not publish message to SQS queue: {e}")
            raise

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        topic = await self._create_sns_topic(topic_name=consumer.message_type)
        queue = await self._create_sqs_queue(queue_name=consumer.message_type)
        await self._update_queue_policy(queue=queue, topic=topic)
        _ = await self._subscribe_queue_to_topic(queue=queue, topic=topic)
        logger.info(f"Registered consumer {consumer.id_}: {consumer.message_type}")

        async def start_consuming_callable() -> None:
            """StartConsumingCallable.

            Consumer of this queue should call this to start consuming messages.
            """
            while True:
                session = self._get_aio_session()
                async with session.create_client(
                    "sqs", region_name=self.region
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

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        """Perform any clean up of queues and messages."""
        session = self._get_aio_session()

        async with session.create_client("sqs", region_name=self.region) as sqs_client, \
                   session.create_client("sns", region_name=self.region) as sns_client:
            
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
