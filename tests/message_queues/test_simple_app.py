from fastapi.testclient import TestClient
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.message_consumers.base import BaseMessageQueueConsumer


def _test_register_consumer() -> None:
    # arrange
    mq = SimpleMessageQueue()
    consumer = BaseMessageQueueConsumer(message_type="mock_type")
    test_client = TestClient(mq._app)

    # act
    response = test_client.post("/register_consumer", json=consumer.model_dump())

    # assert
    assert response.status_code == 200
    assert response.json() == {"consumer": consumer.id_}
