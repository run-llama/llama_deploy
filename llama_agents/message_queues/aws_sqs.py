"""AWS SQS Message Queue."""

import asyncio
import json
from logging import getLogger
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import aiobotocore
from aiobotocore.session import get_session
from botocore.exceptions import ClientError

from llama_agents.message_queues.base import BaseMessageQueue
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.base import BaseMessageQueueConsumer, StartConsumingCallable

if TYPE_CHECKING:
    from aiobotocore.client import AioBaseClient

logger = getLogger(__name__)

DEFAULT_REGION = "us-west-2"
DEFAULT_QUEUE_NAME = "llama-agents"

class SQSMessageQueue(BaseMessageQueue):
    """AWS SQS integration with aiobotocore client.
    
    This class creates and interacts with SQS queues. It includes methods for
    publishing messages to the queue and registering consumers to process messages.

    Attributes:
        region (str): The AWS region where the SQS queue is located.
        queue_name (str): The name of the SQS queue.
    """

    region: str = DEFAULT_REGION
    queue_name: str = DEFAULT_QUEUE_NAME
    _sqs_client: Optional['AioBaseClient'] = None

    def __init__(self, region: str = DEFAULT_REGION, queue_name: str = DEFAULT_QUEUE_NAME) -> None:
        super().__init__(region=region, queue_name=queue_name)
        self._session = get_session()
        self._queue_url = None

    async def _get_queue_url(self, queue_name: str) -> str:
        """Get the URL for the SQS queue."""
        async with self._session.create_client('sqs', region_name=self.region) as client:
            try:
                response = await client.get_queue_url(QueueName=queue_name)
                return response['QueueUrl']
            except ClientError as e:
                logger.error(f"Could not get SQS queue URL: {e}")
                raise

    async def _init_client(self):
        """Initialize SQS client and queue URL."""
        if self._queue_url is None:
            async with self._session.create_client('sqs', region_name=self.region) as client:
                self._sqs_client = client
                self._queue_url = await self._get_queue_url(self.queue_name)

    async def _publish(self, message: QueueMessage) -> Any:
        """Publish message to the SQS queue."""
        message_body = json.dumps(message.model_dump())
        await self._init_client()
        try:
            response = await self._sqs_client.send_message(
                QueueUrl=self._queue_url,
                MessageBody=message_body
            )
            logger.info(f"Published message {message.id_} to queue {self.queue_name}")
            return response
        except ClientError as e:
            logger.error(f"Could not publish message to SQS queue: {e}")
            raise

    async def register_consumer(self, consumer: BaseMessageQueueConsumer) -> StartConsumingCallable:
        """Register a new consumer."""
        logger.info(f"Registered consumer {consumer.id_}: {consumer.message_type}")
        await self._init_client()

        async def start_consuming_callable() -> None:
            """StartConsumingCallable.

            Consumer of this queue should call this to start consuming messages.
            """
            while True:
                try:
                    response = await self._sqs_client.receive_message(
                        QueueUrl=self._queue_url,
                        MaxNumberOfMessages=10,
                        WaitTimeSeconds=20
                    )
                    messages = response.get('Messages', [])
                    for msg in messages:
                        receipt_handle = msg['ReceiptHandle']
                        message_body = json.loads(msg['Body'])
                        queue_message = QueueMessage.model_validate(message_body)
                        await consumer.process_message(queue_message)
                        await self._sqs_client.delete_message(
                            QueueUrl=self._queue_url,
                            ReceiptHandle=receipt_handle
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

    async def cleanup_local(self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]) -> None:
        """Perform any clean up of queues and messages."""
        await self._init_client()
        try:
            async with self._session.create_client('sqs', region_name=self.region) as client:
                for message_type in message_types:
                    await client.purge_queue(QueueUrl=self._queue_url)
            logger.info(f"Purged SQS queue: {self.queue_name}")
        except ClientError as e:
            logger.error(f"Error purging SQS queue: {e}")
