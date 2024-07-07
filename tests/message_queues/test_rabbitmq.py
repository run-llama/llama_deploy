from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue

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


# @pytest.mark.skipif(aio_pika is None, reason="aio_pika not installed")
# @pytest.mark.asyncio()
