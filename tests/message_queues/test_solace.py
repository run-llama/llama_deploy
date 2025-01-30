import json
import os
from typing import Dict, Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from solace.messaging.publisher.persistent_message_publisher import (
    PersistentMessagePublisher,
)
from solace.messaging.receiver.persistent_message_receiver import (
    PersistentMessageReceiver,
)
from solace.messaging.resources.topic import Topic

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.solace import (
    MessageHandlerImpl,
    SolaceMessageQueue,
    SolaceMessageQueueConfig,
)
from llama_deploy.messages.base import QueueMessage


@pytest.fixture(autouse=True)
def setup_env_variables() -> Generator[None, None, None]:
    """Setup environment variables for testing.

    Yields:
        None: Yields control back to the test after setting up environment
    """
    # Save current environment
    old_env: Dict[str, str] = dict(os.environ)

    # Set test environment variables
    os.environ.update(
        {
            "SOLACE_HOST": "localhost:55555",
            "SOLACE_VPN_NAME": "test_vpn",
            "SOLACE_USERNAME": "test_user",
            "SOLACE_PASSWORD": "test_pass",
            "SOLACE_HOST_SECURED": "localhost:55556",
            "SOLACE_IS_QUEUE_TEMPORARY": "true",
        }
    )

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(old_env)


@pytest.fixture
def mock_messaging_service() -> Generator[Mock, None, None]:
    """Create a mock messaging service.

    Returns:
        Mock: Mocked messaging service instance
    """
    with patch("solace.messaging.messaging_service.MessagingService") as mock:
        service_instance = Mock()
        service_instance.is_connected = True
        mock.builder.return_value.from_properties.return_value.with_reconnection_retry_strategy.return_value.build.return_value = service_instance
        yield service_instance


@pytest.fixture
def mock_publisher() -> Mock:
    """Create a mock publisher.

    Returns:
        Mock: Mocked persistent message publisher
    """
    publisher: Mock = Mock(spec=PersistentMessagePublisher)
    publisher.start = Mock()
    publisher.publish = Mock()
    return publisher


@pytest.fixture
def mock_receiver() -> Mock:
    """Create a mock receiver.

    Returns:
        Mock: Mocked persistent message receiver
    """
    receiver: Mock = Mock(spec=PersistentMessageReceiver)
    receiver.start = Mock()
    receiver.add_subscription = Mock()
    receiver.receive_async = Mock()
    return receiver


@pytest.fixture
def solace_queue(
    mock_messaging_service: Mock, mock_publisher: Mock, mock_receiver: Mock
) -> Generator[SolaceMessageQueue, None, None]:
    """Create a Solace queue instance with mocked dependencies.

    Args:
        mock_messaging_service: Mocked messaging service
        mock_publisher: Mocked publisher
        mock_receiver: Mocked receiver

    Returns:
        SolaceMessageQueue: Configured Solace queue instance
    """
    with patch("solace.messaging.messaging_service.MessagingService") as mock_service:
        mock_service.builder.return_value.from_properties.return_value.with_reconnection_retry_strategy.return_value.build.return_value = mock_messaging_service
        mock_messaging_service.create_persistent_message_publisher_builder.return_value.build.return_value = mock_publisher
        mock_messaging_service.create_persistent_message_receiver_builder.return_value.with_missing_resources_creation_strategy.return_value.build.return_value = mock_receiver

        queue = SolaceMessageQueue(SolaceMessageQueueConfig(type="solace"))
        queue._messaging_service = mock_messaging_service
        queue._publisher = mock_publisher
        queue._persistent_receiver = mock_receiver
        yield queue


def test_solace_config(setup_env_variables: None) -> None:
    """Test config initialization with environment variables."""
    config = SolaceMessageQueueConfig()
    properties = config.get_properties()

    assert properties["solace.messaging.transport.host"] == "localhost:55555"
    assert properties["solace.messaging.service.vpn-name"] == "test_vpn"
    assert properties["solace.messaging.authentication.basic.username"] == "test_user"
    assert properties["solace.messaging.authentication.basic.password"] == "test_pass"
    assert properties["solace.messaging.transport.host.secured"] == "localhost:55556"
    assert properties["IS_QUEUE_TEMPORARY"] is True


@pytest.mark.asyncio
async def test_establish_connection(
    solace_queue: SolaceMessageQueue, mock_messaging_service: Mock, mock_publisher: Mock
) -> None:
    """Test establishing connection to Solace server."""
    connect_result = await solace_queue._establish_connection()

    assert connect_result is not None
    mock_messaging_service.connect.assert_called_once()
    mock_publisher.start.assert_called_once()
    assert solace_queue._publisher.set_message_publish_receipt_listener.called  # type: ignore


@pytest.mark.asyncio
async def test_publish_message(
    solace_queue: SolaceMessageQueue, mock_publisher: Mock
) -> None:
    """Test publishing a message to Solace."""
    test_message = QueueMessage(id_="test_id", type="test_type")

    await solace_queue._publish(test_message, "test_topic")

    mock_publisher.publish.assert_called_once()
    call_args = mock_publisher.publish.call_args
    assert isinstance(call_args[1]["destination"], Topic)
    assert json.loads(call_args[1]["message"])["id_"] == "test_id"


@pytest.mark.asyncio
async def test_register_consumer(
    solace_queue: SolaceMessageQueue, mock_receiver: Mock
) -> None:
    """Test registering a consumer."""
    mock_consumer = Mock(spec=BaseMessageQueueConsumer)
    mock_consumer.message_type = "test_topic"

    start_consuming = await solace_queue.register_consumer(mock_consumer, "test_topic")

    assert callable(start_consuming)
    mock_receiver.receive_async.assert_called_once()
    mock_receiver.add_subscription.assert_called_once()


@pytest.mark.asyncio
async def test_deregister_consumer(
    solace_queue: SolaceMessageQueue, mock_receiver: Mock
) -> None:
    """Test deregistering a consumer."""
    with patch("llama_deploy.message_queues.solace.MAX_SLEEP", 0.1):
        mock_consumer = Mock(spec=BaseMessageQueueConsumer)
        mock_consumer.message_type = "test_topic"

        await solace_queue.deregister_consumer(mock_consumer)

        mock_receiver.remove_subscription.assert_called_once()
        mock_receiver.terminate.assert_called_once()


def test_disconnect(
    solace_queue: SolaceMessageQueue, mock_messaging_service: Mock
) -> None:
    """Test disconnecting from Solace server."""
    solace_queue.disconnect()
    mock_messaging_service.disconnect.assert_called_once()


def test_is_connected(
    solace_queue: SolaceMessageQueue, mock_messaging_service: Mock
) -> None:
    """Test checking connection status."""
    assert solace_queue.is_connected() == mock_messaging_service.is_connected


def test_bind_to_queue(solace_queue: SolaceMessageQueue, mock_receiver: Mock) -> None:
    """Test binding to a queue."""
    subscriptions: list[str] = ["test_topic"]
    solace_queue.bind_to_queue(subscriptions)

    mock_receiver.start.assert_called_once()
    mock_receiver.add_subscription.assert_called_once()


def test_message_handler_impl() -> None:
    """Test message handler implementation."""
    mock_consumer = Mock(spec=BaseMessageQueueConsumer)
    mock_consumer.process_message = AsyncMock()
    mock_receiver = Mock(spec=PersistentMessageReceiver)

    handler = MessageHandlerImpl(mock_consumer, mock_receiver)

    mock_message = Mock()
    mock_message.get_destination_name.return_value = "test_topic"
    mock_message.get_payload_as_string.return_value = json.dumps(
        {"id_": "test_id", "type": "test_type"}
    )
    mock_message.get_correlation_id.return_value = "test_correlation_id"

    handler.on_message(mock_message)

    mock_consumer.process_message.assert_called_once()
    mock_receiver.ack.assert_called_once_with(mock_message)
