import asyncio
import json
import pytest
from pydantic import PrivateAttr
from typing import Any, List
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step

from llama_deploy.messages import QueueMessage
from llama_deploy.message_consumers import BaseMessageQueueConsumer
from llama_deploy.message_queues import SimpleMessageQueue
from llama_deploy.services.workflow import WorkflowService
from llama_deploy.types import CONTROL_PLANE_NAME, ActionTypes, TaskDefinition


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.fixture()
def human_output_consumer() -> MockMessageConsumer:
    return MockMessageConsumer(message_type=CONTROL_PLANE_NAME)


@pytest.fixture()
def test_workflow() -> Workflow:
    class TestWorklow(Workflow):
        @step()
        async def run_step(self, ev: StartEvent) -> StopEvent:
            arg1 = ev.get("arg1")
            if not arg1:
                raise ValueError("arg1 is required.")

            return StopEvent(result=str(arg1) + "_result")

    return TestWorklow()


@pytest.mark.asyncio
async def test_workflow_service(
    test_workflow: Workflow, human_output_consumer: MockMessageConsumer
) -> None:
    message_queue = SimpleMessageQueue()
    _ = await message_queue.register_consumer(human_output_consumer)

    # create the service
    workflow_service = WorkflowService(
        test_workflow,
        message_queue,
        service_name="test_workflow",
        description="Test Workflow Service",
        host="localhost",
        port=8001,
    )

    # launch it
    mq_task = await message_queue.launch_local()
    server_task = await workflow_service.launch_local()

    # pass a task to the service
    task = TaskDefinition(
        input=json.dumps({"arg1": "test_arg1"}),
        session_id="test_session_id",
    )

    await workflow_service.process_message(
        QueueMessage(
            action=ActionTypes.NEW_TASK,
            data=task.model_dump(),
        )
    )

    # let the service process the message
    await asyncio.sleep(1)
    mq_task.cancel()
    server_task.cancel()

    # check the result
    result = human_output_consumer.processed_messages[-1]
    assert result.action == ActionTypes.COMPLETED_TASK
    assert result.data["result"] == "test_arg1_result"
