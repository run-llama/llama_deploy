"""Solace Message Queue."""

import asyncio
import json
import time
from string import Template
from logging import getLogger
from typing import Any, Dict, List, Literal, TYPE_CHECKING

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from llama_deploy.message_queues.base import BaseMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.message_consumers.base import (
    BaseMessageQueueConsumer,
    StartConsumingCallable,
)

if TYPE_CHECKING:
    from solace.messaging.receiver.message_receiver import InboundMessage
    from solace.messaging.publisher.persistent_message_publisher import PublishReceipt
    from solace.messaging.connections.connectable import Connectable
    from solace.messaging.messaging_service import MessagingService
    from solace.messaging.receiver.persistent_message_receiver import (
        PersistentMessageReceiver,
    )
    from solace.messaging.publisher.persistent_message_publisher import (
        PersistentMessagePublisher,
    )

# Constants
MAX_SLEEP = 10
QUEUE_TEMPLATE = Template("Q/$iteration")

# Configure logger
logger = getLogger(__name__)

SOLACE_INSTALLED = True

try:
    from solace.messaging.publisher.persistent_message_publisher import (
        MessagePublishReceiptListener,
    )
    from solace.messaging.receiver.message_receiver import MessageHandler
    from solace.messaging.messaging_service import MessagingService
    from solace.messaging.receiver.persistent_message_receiver import (
        PersistentMessageReceiver,
    )
    from solace.messaging.publisher.persistent_message_publisher import (
        PersistentMessagePublisher,
    )

    class MessagePublishReceiptListenerImpl(MessagePublishReceiptListener):
        """Message publish receipt listener for Solace message queue."""

        def __init__(self, callback: Any = None) -> None:
            self.callback = callback

        def on_publish_receipt(self, publish_receipt: "PublishReceipt") -> None:
            if publish_receipt.user_context:
                logger.info(
                    f"\tUser context received: {publish_receipt.user_context.get_custom_message}"
                )
                callback = publish_receipt.user_context.get("callback")
                callback(publish_receipt.user_context)

    class MessageHandlerImpl(MessageHandler):
        """Message handler for Solace message queue."""

        def __init__(
            self,
            consumer: BaseMessageQueueConsumer,
            receiver: PersistentMessageReceiver = None,
        ) -> None:
            self._consumer = consumer
            self._receiver = receiver

        def on_message(self, message: "InboundMessage") -> None:
            try:
                topic = message.get_destination_name()
                payload_as_string = message.get_payload_as_string()
                correlation_id = message.get_correlation_id()

                message_details = {
                    "topic": topic,
                    "payload": payload_as_string,
                    "correlation_id": correlation_id,
                }

                # Log the consumed message in JSON format
                logger.debug(
                    f"Consumed message: {json.dumps(message_details, indent=2)}"
                )

                # Parse the payload and validate the queue message
                queue_message_data = json.loads(payload_as_string)
                queue_message = QueueMessage.model_validate(queue_message_data)

                # Process the message using the consumer
                asyncio.run(self._consumer.process_message(queue_message))

                if self._receiver:
                    self._receiver.ack(message)

            except Exception as unexpected_error:
                logger.error(f"Error consuming message: {unexpected_error}")

except ImportError:
    SOLACE_INSTALLED = False


class SolaceMessageQueueConfig(BaseSettings):
    """Solace PubSub+ message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="SOLACE_")
    type: Literal["solace"] = Field(default="solace", exclude=True)
    host: str = Field(default="")
    vpn_name: str = Field(default="")
    username: str = Field(default="")
    password: str = Field(default="")
    host_secured: str = Field(default="")
    is_queue_temporary: bool = Field(default=True)

    def get_properties(self) -> dict:
        """Reads Solace PubSub+ properties from environment variables."""
        HOST = "solace.messaging.transport.host"
        VPN_NAME = "solace.messaging.service.vpn-name"
        USER_NAME = "solace.messaging.authentication.basic.username"
        PASSWORD = "solace.messaging.authentication.basic.password"
        HOST_SECURED = "solace.messaging.transport.host.secured"
        IS_QUEUE_TEMPORARY = "IS_QUEUE_TEMPORARY"

        broker_properties = {
            HOST: self.host,
            VPN_NAME: self.vpn_name,
            USER_NAME: self.username,
            PASSWORD: self.password,
            HOST_SECURED: self.host_secured,
            IS_QUEUE_TEMPORARY: self.is_queue_temporary,
        }

        logger.info(
            f"\n\n********************************BROKER PROPERTIES**********************************************"
            f"\nHost: {broker_properties.get(HOST)}"
            f"\nSecured Host: {broker_properties.get(HOST_SECURED)}"
            f"\nVPN: {broker_properties.get(VPN_NAME)}"
            f"\nUsername: {broker_properties.get(USER_NAME)}"
            f"\nPassword: XXXXXXXX"
            f"\nIs Queue Temporary: {broker_properties.get(IS_QUEUE_TEMPORARY)}"
            f"\n***********************************************************************************************\n"
        )
        return broker_properties


class SolaceMessageQueue(BaseMessageQueue):
    """Solace PubSub+ Message Queue."""

    messaging_service: "MessagingService" = None
    publisher: "PersistentMessagePublisher" = None
    persistent_receiver: "PersistentMessageReceiver" = None
    broker_properties: dict = {}
    is_queue_temporary: bool = True

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the Solace message queue."""
        if not SOLACE_INSTALLED:
            raise ValueError(
                "Missing `solace` package. Please install by running `pip install llama-deploy[solace]`."
            )

        from solace.messaging.config.retry_strategy import RetryStrategy
        from solace.messaging.messaging_service import MessagingService

        super().__init__()

        config = SolaceMessageQueueConfig(**kwargs)
        self.broker_properties = config.get_properties()
        self.messaging_service = (
            MessagingService.builder()
            .from_properties(self.broker_properties)
            .with_reconnection_retry_strategy(
                RetryStrategy.parametrized_retry(20, 3000)
            )
            .build()
        )
        self.is_queue_temporary = bool(self.broker_properties.get("IS_QUEUE_TEMPORARY"))
        logger.info("Solace Messaging Service created")

    def __del__(self) -> None:
        self.disconnect()

    async def _establish_connection(self) -> "Connectable":
        """Establish and return a new connection to the Solace server."""

        try:
            from solace.messaging.errors.pubsubplus_client_error import (
                PubSubPlusClientError,
            )
        except ImportError:
            raise ValueError(
                "Missing `solace` package. Please install by running `pip install llama-deploy[solace]`."
            )

        try:
            logger.info("Establishing connection to Solace server")
            connect = self.messaging_service.connect()

            # Create a publisher
            self.publisher = self.messaging_service.create_persistent_message_publisher_builder().build()
            self.publisher.start()

            publish_receipt_listener = MessagePublishReceiptListenerImpl()
            self.publisher.set_message_publish_receipt_listener(
                publish_receipt_listener
            )

            logger.info("Connected to Solace server")
            return connect
        except PubSubPlusClientError as exception:
            logger.error(f"Failed to establish connection: {exception}")
            raise

    async def _publish(self, message: QueueMessage, topic: str) -> None:
        """Publish message to the queue."""
        try:
            from solace.messaging.resources.topic import Topic
        except ImportError:
            raise ValueError(
                "Missing `solace` package. Please install by running `pip install llama-deploy[solace]`."
            )

        if not self.is_connected():
            await self._establish_connection()

        logger.debug(f"Publishing message: {message}")
        destination = Topic.of(topic)
        message_body = json.dumps(message.model_dump())

        try:
            self.publisher.publish(
                message=message_body,
                destination=destination,
            )

            logger.debug(f"Published message: {message.id_}")
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from the Solace server."""
        try:
            self.messaging_service.disconnect()
            logger.info("Disconnected from Solace server")
        except Exception as exception:
            logger.debug("Error disconnecting: %s", exception)

    def is_connected(self) -> bool:
        """Check if the Solace server is connected."""
        return self.messaging_service.is_connected

    def bind_to_queue(self, subscriptions: list = []) -> None:
        """Bind to a queue and subscribe to topics."""
        try:
            from solace.messaging.errors.pubsubplus_client_error import (
                PubSubPlusClientError,
            )
            from solace.messaging.config.missing_resources_creation_configuration import (
                MissingResourcesCreationStrategy,
            )
            from solace.messaging.resources.queue import Queue
        except ImportError:
            raise ValueError(
                "Missing `solace` package. Please install by running `pip install llama-deploy[solace]`."
            )

        if subscriptions is None:
            return
        queue_name = QUEUE_TEMPLATE.substitute(iteration=subscriptions[0])

        if self.is_queue_temporary:
            queue = Queue.non_durable_exclusive_queue(queue_name)
        else:
            queue = Queue.durable_exclusive_queue(queue_name)

        try:
            # Build a receiver and bind it to the queue
            self.persistent_receiver = (
                self.messaging_service.create_persistent_message_receiver_builder()
                .with_missing_resources_creation_strategy(
                    MissingResourcesCreationStrategy.CREATE_ON_START
                )
                .build(queue)
            )
            self.persistent_receiver.start()

            logger.debug(
                "Persistent receiver started... Bound to Queue [%s] (Temporary: %s)",
                queue.get_name(),
                self.is_queue_temporary,
            )

        # Handle API exception
        except PubSubPlusClientError as exception:
            logger.error(
                "Error creating persistent receiver for queue [%s], %s",
                queue_name,
                exception,
            )

        # If subscriptions are provided, add them to the receiver
        if subscriptions:
            for subscription in subscriptions:
                self.persistent_receiver.add_subscription(subscription)
                logger.info("Subscribed to topic: %s", subscription)

        return

    async def register_consumer(
        self, consumer: BaseMessageQueueConsumer, topic: str | None = None
    ) -> StartConsumingCallable:
        """Register a new consumer."""
        try:
            from solace.messaging.errors.pubsubplus_client_error import (
                PubSubPlusClientError,
                IllegalStateError,
            )
            from solace.messaging.resources.topic_subscription import TopicSubscription
        except ImportError:
            raise ValueError(
                "Missing `solace` package. Please install by running `pip install llama-deploy[solace]`."
            )

        consumer_subscription = topic
        subscriptions = [TopicSubscription.of(consumer_subscription)]

        try:
            if not self.is_connected():
                await self._establish_connection()

            self.bind_to_queue(subscriptions=subscriptions)
            logger.info(f"Consumer registered to: {consumer_subscription}")
            self.persistent_receiver.receive_async(
                MessageHandlerImpl(consumer=consumer, receiver=self.persistent_receiver)
            )

            async def start_consuming_callable() -> None:
                await asyncio.Future()

            return start_consuming_callable
        except (PubSubPlusClientError, IllegalStateError) as e:
            logger.error(f"Failed to register consumer: {e}")
            raise

    async def deregister_consumer(self, consumer: BaseMessageQueueConsumer) -> None:
        """Deregister a consumer."""
        try:
            from solace.messaging.resources.topic_subscription import TopicSubscription
        except ImportError:
            raise ValueError(
                "Missing `solace` package. Please install by running `pip install llama-deploy[solace]`."
            )

        consumer_subscription = consumer.message_type
        topics = [TopicSubscription.of(consumer_subscription)]

        try:
            for topic in topics:
                self.persistent_receiver.remove_subscription(topic)

            logger.info(f"Consumer deregistered from: {consumer_subscription}")
            time.sleep(MAX_SLEEP)
        except Exception as e:
            logger.error(f"Failed to deregister consumer: {e}")
            raise
        finally:
            self.persistent_receiver.terminate()

    async def processing_loop(self) -> None:
        """A loop for getting messages from queues and sending to consumer."""
        pass

    async def launch_local(self) -> asyncio.Task:
        """Launch the message queue locally, in-process."""
        return asyncio.create_task(self.processing_loop())

    async def launch_server(self) -> None:
        """Launch the message queue server."""
        pass

    async def cleanup_local(
        self, message_types: List[str], *args: Any, **kwargs: Dict[str, Any]
    ) -> None:
        """Perform any clean up of queues and exchanges."""
        pass

    def as_config(self) -> BaseModel:
        """Return the configuration of the Solace message queue."""
        return SolaceMessageQueueConfig()
