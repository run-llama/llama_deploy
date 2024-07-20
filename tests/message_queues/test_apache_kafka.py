from llama_agents.message_queues.apache_kafka import KafkaMessageQueue


try:
    import aiokafka
except (ModuleNotFoundError, ImportError):
    aiokafka = None


def test_init() -> None:
    # arrange/act
    mq = KafkaMessageQueue(url="0.0.0.0:5555")

    # assert
    assert mq.url == "0.0.0.0:5555"
