import asyncio
import pytest
from typing import Any, List
from agentfile.services import HumanService
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.message_consumers.base import BaseMessageQueueConsumer
from agentfile.messages.base import QueueMessage
from agentfile.types import HumanRequest
from llama_index.core.bridge.pydantic import PrivateAttr


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.mark.asyncio()
async def test_init() -> None:
    # arrange
    # act
    human_service = HumanService(
        message_queue=SimpleMessageQueue(),
        running=False,
        description="Test Human Service",
        service_name="Test Human Service",
        step_interval=0.5,
    )

    # assert
    assert not human_service.running
    assert human_service.description == "Test Human Service"
    assert human_service.service_name == "Test Human Service"
    assert human_service.step_interval == 0.5


@pytest.mark.asyncio()
async def test_create_human_req() -> None:
    # arrange
    human_service = HumanService(
        message_queue=SimpleMessageQueue(),
        running=False,
        description="Test Human Service",
        service_name="Test Human Service",
        step_interval=0.5,
    )
    req = HumanRequest(id_="1", input="Mock human req.", source_id="another human")

    # act
    result = await human_service.create_human_request(req)

    # assert
    assert result == {"human_request_id": req.id_}
    assert human_service._outstanding_human_requests[req.id_] == req