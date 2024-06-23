import asyncio
import pytest
from fastapi.testclient import TestClient
from pydantic import PrivateAttr
from typing import Any, List
from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.messages.base import QueueMessage
from llama_agents.message_consumers.remote import (
    RemoteMessageConsumerDef,
    BaseMessageQueueConsumer,
)
from llama_agents.types import ActionTypes


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


def test_register_consumer() -> None:
    # arrange
    mq = SimpleMessageQueue()
    remote_consumer_def = RemoteMessageConsumerDef(
        message_type="mock_type", url="https://mock-url.io"
    )
    test_client = TestClient(mq._app)

    # act
    response = test_client.post(
        "/register_consumer", json=remote_consumer_def.model_dump()
    )

    # assert
    assert response.status_code == 200
    assert response.json() == {"consumer": remote_consumer_def.id_}
    assert len(mq.consumers) == 1


def test_deregister_consumer() -> None:
    # arrange
    mq = SimpleMessageQueue()
    remote_consumer_def = RemoteMessageConsumerDef(
        message_type="mock_type", url="https://mock-url.io"
    )
    test_client = TestClient(mq._app)

    # act
    _ = test_client.post("/register_consumer", json=remote_consumer_def.model_dump())
    response = test_client.post(
        "/deregister_consumer", json=remote_consumer_def.model_dump()
    )

    # assert
    assert response.status_code == 200
    assert len(mq.consumers) == 0


def test_get_consumers() -> None:
    # arrange
    mq = SimpleMessageQueue()
    remote_consumer_def = RemoteMessageConsumerDef(
        message_type="mock_type", url="https://mock-url.io"
    )
    test_client = TestClient(mq._app)

    # act
    _ = test_client.post("/register_consumer", json=remote_consumer_def.model_dump())
    response = test_client.get("/get_consumers/?message_type=mock_type")

    # assert
    assert response.status_code == 200
    assert response.json() == [remote_consumer_def.model_dump()]


@pytest.mark.asyncio
async def test_publish() -> None:
    # arrange
    mq = SimpleMessageQueue()
    consumer = MockMessageConsumer(message_type="mock_type")
    await mq.register_consumer(consumer)

    test_client = TestClient(mq._app)

    # act
    message = QueueMessage(
        type="mock_type", data={"payload": "mock payload"}, action=ActionTypes.NEW_TASK
    )
    print(message.model_dump())
    response = test_client.post("/publish", json=message.model_dump())

    # assert
    print(response.content)
    assert response.status_code == 200
    assert mq.queues["mock_type"][0] == message
