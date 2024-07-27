"""AWS SQS Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import Any, Dict, List, TYPE_CHECKING, Tuple
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

if TYPE_CHECKING:
    from aiobotocore.session import AioSession

logger = getLogger(__name__)

DEFAULT_REGION = "us-east-1"
DEFAULT_MESSAGE_GROUP_ID = "llama-agents"

TopicArn = str
QueueArn = str
QueueUrl = str
SubscriptionArn = str

logger = getLogger(__name__)


class SQSMessageQueue(BaseMessageQueue):
    """AWS SQS integration with aiobotocore client.

    This class creates and interacts with SQS queues. It includes methods for
    publishing messages to the queue and registering consumers to process messages.

    Attributes:
        region (str): The AWS region where the SQS queue is located.
        queue_name (str): The name of the SQS queue.
    """

    region: str = DEFAULT_REGION
    message_group_id: str = DEFAULT_MESSAGE_GROUP_ID
    topic_arns: Dict[str, str] = {}
    subscription_arns: List[str] = []

    def _get_aio_session(self) -> "AioSession":
        try:
            from aiobotocore.session import get_session
        except ImportError:
            raise ValueError(
                "Missing `aiobotocore`. Please install by running `pip install aiobotocore`."
            )

        return get_session()

    async def _create_sns_topic(self, topic_name: str) -> TopicArn:
        """Create AWS SNS topic."""
        session = self._get_aio_session()
        async with session.create_client("sns", region_name=self.region) as client:
            response = await client.create_topic(
                Name=f"{topic_name}.fifo", Attributes={"FifoTopic": "true"}
            )
        self.topic_arns[topic_name] = response["TopicArn"]
        return response["TopicArn"]

    async def _create_sqs_queue(self, queue_name: str) -> Tuple[QueueUrl, QueueArn]:
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
            return queue_url, queue_arn

    async def _update_queue_policy(
        self, queue_arn: str, queue_url: str, topic_arn: str
    ) -> None:
        session = self._get_aio_session()
        async with session.create_client("sqs", region_name=self.region) as client:
            attributes = get_attributes_with_topic_policy(
                queue_arn=queue_arn, topic_arn=topic_arn
            )
            _ = await client.set_queue_attributes(
                QueueUrl=queue_url, Attributes=attributes
            )

    async def _subscribe_queue_to_topic(
        self, topic_arn: str, queue_arn: str
    ) -> SubscriptionArn:
        """Subscribe queue to topic."""
        session = self._get_aio_session()
        async with session.create_client("sns", region_name=self.region) as client:
            response = await client.subscribe(
                TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn
            )
        return response["SubscriptionArn"]

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to the SQS queue."""
        message_body = json.dumps(message.model_dump())
        topic_arn = self.topic_arns[message.type]
        session = self._get_aio_session()
        try:
            async with session.create_client("sns", region_name=self.region) as client:
                response = await client.publish(
                    TopicArn=topic_arn,
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
        topic_arn = await self._create_sns_topic(topic_name=consumer.message_type)
        queue_url, queue_arn = await self._create_sqs_queue(
            queue_name=consumer.message_type
        )
        await self._update_queue_policy(
            queue_arn=queue_arn, queue_url=queue_url, topic_arn=topic_arn
        )
        susbscription_arn = await self._subscribe_queue_to_topic(
            topic_arn=topic_arn, queue_arn=queue_arn
        )
        if susbscription_arn not in self.subscription_arns:
            self.subscription_arns.append(susbscription_arn)
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
                            QueueUrl=queue_url,
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
                                QueueUrl=queue_url, ReceiptHandle=receipt_handle
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
        pass
