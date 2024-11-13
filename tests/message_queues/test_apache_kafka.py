import json
from unittest.mock import AsyncMock, patch

import pytest

from llama_deploy import QueueMessage
from llama_deploy.message_queues.apache_kafka import (
    KafkaMessageQueue,
    KafkaMessageQueueConfig,
)

try:
    import aiokafka
except (ModuleNotFoundError, ImportError):
    aiokafka = None


def test_init() -> None:
    # arrange/act
    mq = KafkaMessageQueue(KafkaMessageQueueConfig(url="0.0.0.0:5555"))

    # assert
    assert mq._config.url == "0.0.0.0:5555"


def test_from_url_params() -> None:
    # arrange
    host = "mock-host"
    port = 8080

    # act
    mq = KafkaMessageQueue.from_url_params(host=host, port=port)

    # assert
    assert mq._config.url == f"{host}:{port}"


@pytest.mark.asyncio()
@pytest.mark.skipif(aiokafka is None, reason="aiokafka not installed")
async def test_publish() -> None:
    from aiokafka import AIOKafkaProducer

    # Arrange
    mq = KafkaMessageQueue()

    # message types
    queue_message = QueueMessage(publisher_id="test", id_="1")
    message_body = json.dumps(queue_message.model_dump()).encode("utf-8")

    with patch.object(AIOKafkaProducer, "start", new_callable=AsyncMock) as mock_start:
        with patch.object(
            AIOKafkaProducer, "send_and_wait", new_callable=AsyncMock
        ) as mock_send_and_wait:
            # Act
            _ = await mq._publish(queue_message, "test")

            # Assert
            mock_start.assert_awaited_once()
            mock_send_and_wait.assert_awaited_once_with("test", message_body)
