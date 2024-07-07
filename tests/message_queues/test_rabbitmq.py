import pytest
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue
from unittest.mock import patch, MagicMock

try:
    import aio_pika
except ImportError:
    aio_pika = None


def test_init() -> None:
    # arrange/act
    mq = RabbitMQMessageQueue(
        url="amqp://guest:password@rabbitmq", exchange_name="test-exchange"
    )

    # assert
    assert mq.url == "amqp://guest:password@rabbitmq"
    assert mq.exchange_name == "test-exchange"


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
    assert mq.url == f"amqp://{username}:{password}@{host}/{vhost}"
    assert mq.exchange_name == exchange_name


@pytest.mark.asyncio()
@pytest.mark.skipif(aio_pika is None, reason="aio_pika not installed")
@patch("llama_agents.message_queues.rabbitmq._establish_connection")
async def test_establish_connection(mock_connect: MagicMock) -> None:
    # arrange
    mq = RabbitMQMessageQueue()
    mock_connect.return_value = None

    # act
    _ = await mq.new_connection()

    # assert
    mock_connect.assert_called_once_with("amqp://guest:guest@localhost/")
