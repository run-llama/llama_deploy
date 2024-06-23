from fastapi.testclient import TestClient
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.message_consumers.remote import (
    RemoteMessageConsumerDef,
)


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
