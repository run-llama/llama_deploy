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


# @pytest.mark.skipif(aio_pika is None, reason="aio_pika not installed")
# @pytest.mark.asyncio()
