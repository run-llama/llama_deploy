import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llama_deploy import QueueMessage
from llama_deploy.message_queues.rabbitmq import (
    RabbitMQMessageQueue,
    RabbitMQMessageQueueConfig,
)

try:
    import aio_pika
    from aio_pika import DeliveryMode
    from aio_pika import Message as AioPikaMessage
except (ModuleNotFoundError, ImportError):
    aio_pika = None  # type: ignore


def test_init() -> None:
    # arrange/act
    mq = RabbitMQMessageQueue(
        RabbitMQMessageQueueConfig(
            url="amqp://guest:password@rabbitmq", exchange_name="test-exchange"
        )
    )

    # assert
    assert mq._config.url == "amqp://guest:password@rabbitmq"
    assert mq._config.exchange_name == "test-exchange"


def test_from_url_params() -> None:
    # arrange
    username = "mock-user"
    password = "mock-pass"
    host = "mock-host"
    vhost = "mock-vhost"
    exchange_name = "mock-exchange"

    # act
    mq = RabbitMQMessageQueue.from_url_params(
        username=username,
        password=password,
        host=host,
        vhost=vhost,
        exchange_name=exchange_name,
    )

    # assert
    assert mq._config.url == f"amqp://{username}:{password}@{host}/{vhost}"
    assert mq._config.exchange_name == exchange_name


@pytest.mark.asyncio()
@pytest.mark.skipif(aio_pika is None, reason="aio_pika not installed")
@patch("llama_deploy.message_queues.rabbitmq._establish_connection")
async def test_establish_connection(mock_connect: MagicMock) -> None:
    # arrange
    mq = RabbitMQMessageQueue()
    mock_connect.return_value = None

    # act
    _ = await mq.new_connection()

    # assert
    mock_connect.assert_called_once_with("amqp://guest:guest@localhost/")


@pytest.mark.asyncio()
@pytest.mark.skipif(aio_pika is None, reason="aio_pika not installed")
@patch("llama_deploy.message_queues.rabbitmq._establish_connection")
async def test_publish(mock_connect: MagicMock) -> None:
    # Arrange
    mq = RabbitMQMessageQueue()
    # mocks
    mock_exchange_publish = AsyncMock()
    mock_connect.return_value.channel.return_value.declare_exchange.return_value.publish = mock_exchange_publish
    # message types
    queue_message = QueueMessage(publisher_id="test", id_="1")
    message_body = json.dumps(queue_message.model_dump()).encode("utf-8")
    aio_pika_message = AioPikaMessage(
        message_body, delivery_mode=DeliveryMode.PERSISTENT
    )

    # Act
    _ = await mq._publish(queue_message, topic="test")

    # Assert
    mock_connect.assert_called_once()
    mock_exchange_publish.assert_called_once()
    args, kwargs = mock_exchange_publish.call_args
    assert args[0].body == aio_pika_message.body
    assert args[0].body_size == aio_pika_message.body_size
    assert args[0].delivery_mode == aio_pika_message.delivery_mode
    assert kwargs["routing_key"] == queue_message.type
