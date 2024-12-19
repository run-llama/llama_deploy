import asyncio

import pytest
from fastapi.testclient import TestClient

from llama_deploy.message_queues.simple import (
    SimpleMessageQueue,
    SimpleMessageQueueConfig,
)
from llama_deploy.messages.base import QueueMessage

from .conftest import MockMessageConsumer


def test_home(http_client: TestClient) -> None:
    response = http_client.get("/")
    assert response.status_code == 200
    assert response.json() == {
        "description": "Message queue for multi-agent system",
        "service_name": "message_queue",
    }


def test_create_topic(http_client: TestClient):
    response = http_client.post("/topics/test_topic")
    assert response.status_code == 200
    response = http_client.post("/topics/test_topic")
    assert response.status_code == 409


def test_publish(http_client: TestClient):
    response = http_client.post("/messages/foo", json=QueueMessage().model_dump())
    assert response.status_code == 404


def test_get_messages(http_client: TestClient):
    response = http_client.get("/messages/foo")
    assert response.status_code == 404


@pytest.mark.asyncio()
async def test_roundtrip(message_queue_server) -> None:
    # Arrange
    mq = SimpleMessageQueue(SimpleMessageQueueConfig(raise_exceptions=True))

    consumer_one = MockMessageConsumer(message_type="test_one")
    consumer_one_fn = await mq.register_consumer(consumer_one)
    consumer_one_task = asyncio.create_task(consumer_one_fn())

    consumer_two = MockMessageConsumer(message_type="test_two")
    consumer_two_fn = await mq.register_consumer(consumer_two)
    consumer_two_task = asyncio.create_task(consumer_two_fn())

    # Act
    await mq.publish(
        QueueMessage(publisher_id="test", id_="1", type="test_one"), topic="test_one"
    )
    await mq.publish(
        QueueMessage(publisher_id="test", id_="2", type="test_one"), topic="test_one"
    )
    await mq.publish(
        QueueMessage(publisher_id="test", id_="3", type="test_two"), topic="test_two"
    )

    # Give some time for last message to get published and sent to consumers
    await asyncio.sleep(1)

    consumer_one_task.cancel()
    consumer_two_task.cancel()

    await asyncio.gather(consumer_one_task, consumer_two_task)

    # Assert
    assert ["1", "2"] == [m.id_ for m in consumer_one.processed_messages]
    assert ["3"] == [m.id_ for m in consumer_two.processed_messages]
