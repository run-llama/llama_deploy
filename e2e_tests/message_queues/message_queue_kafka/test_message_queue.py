import asyncio
import subprocess
from pathlib import Path

import pytest

from llama_deploy.message_consumers.callable import CallableMessageConsumer
from llama_deploy.message_queues import KafkaMessageQueue, KafkaMessageQueueConfig
from llama_deploy.messages import QueueMessage


@pytest.fixture
def kafka_service():
    cwd = Path(__file__).resolve().parent
    proc = subprocess.Popen(["docker-compose", "up", "-d", "--wait"], cwd=cwd)
    proc.communicate()
    yield
    subprocess.Popen(["docker-compose", "down"], cwd=cwd)


@pytest.fixture
def mq(kafka_service):
    return KafkaMessageQueue(KafkaMessageQueueConfig(topic_name="test"))


@pytest.mark.asyncio
async def test_roundtrip(mq):
    received_messages = []

    # register a consumer
    def message_handler(message: QueueMessage) -> None:
        received_messages.append(message)

    test_consumer = CallableMessageConsumer(
        message_type="test", handler=message_handler
    )
    start_consuming_callable = await mq.register_consumer(test_consumer)

    # produce a message
    test_message = QueueMessage(type="test", data={"message": "this is a test"})

    # await asyncio.gather(start_consuming_callable(), mq.publish(test_message))
    await mq.publish(test_message)
    t = asyncio.create_task(start_consuming_callable())
    await asyncio.sleep(0.5)
    # at this point message should've been arrived
    t.cancel()

    assert len(received_messages) == 1
    assert test_message in received_messages
