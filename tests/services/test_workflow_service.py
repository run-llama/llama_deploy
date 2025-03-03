import asyncio
import json
from typing import Any, List

import pytest
from llama_index.core.workflow import StartEvent, StopEvent, Workflow, step
from llama_index.core.workflow.context_serializers import JsonSerializer
from llama_index.core.workflow.events import HumanResponseEvent, InputRequiredEvent
from pydantic import PrivateAttr

from llama_deploy.message_consumers import BaseMessageQueueConsumer
from llama_deploy.message_queues import SimpleMessageQueue
from llama_deploy.messages import QueueMessage
from llama_deploy.services.workflow import WorkflowService, WorkflowServiceConfig
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


@pytest.fixture()
def test_hitl_workflow() -> Workflow:
    class TestHumanInTheLoopWorklow(Workflow):
        @step
        async def step1(self, ev: StartEvent) -> InputRequiredEvent:
            return InputRequiredEvent(prefix="Enter a number: ")

        @step
        async def step2(self, ev: HumanResponseEvent) -> StopEvent:
            return StopEvent(result=ev.response)

    return TestHumanInTheLoopWorklow()


@pytest.mark.asyncio
async def test_workflow_service(
    test_workflow: Workflow,
    human_output_consumer: MockMessageConsumer,
    message_queue_server: Any,
) -> None:
    message_queue = SimpleMessageQueue()
    consumer_fn = await message_queue.register_consumer(
        human_output_consumer, topic="llama_deploy.control_plane"
    )
    consumer_task = asyncio.create_task(consumer_fn())

    # create the service
    workflow_service = WorkflowService(
        test_workflow,
        message_queue,  # type: ignore
        config=WorkflowServiceConfig(
            service_name="test_workflow",
            description="Test Workflow Service",
            host="localhost",
            port=8001,
        ),
    )
    service_task = asyncio.create_task(workflow_service.processing_loop())

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
    consumer_task.cancel()
    service_task.cancel()
    await asyncio.gather(consumer_task, service_task)

    # check the result
    result = human_output_consumer.processed_messages[-1]
    assert result.action == ActionTypes.COMPLETED_TASK
    assert result.data["result"] == "test_arg1_result"


@pytest.mark.asyncio()
async def test_hitl_workflow_service(
    test_hitl_workflow: Workflow,
    human_output_consumer: MockMessageConsumer,
    message_queue_server: Any,
) -> None:
    # arrange
    message_queue = SimpleMessageQueue()
    consumer_fn = await message_queue.register_consumer(
        human_output_consumer, topic="llama_deploy.control_plane"
    )
    consumer_task = asyncio.create_task(consumer_fn())

    # create the service
    workflow_service = WorkflowService(
        test_hitl_workflow,
        message_queue,  # type: ignore
        config=WorkflowServiceConfig(
            service_name="test_workflow",
            description="Test Workflow Service",
            host="localhost",
            port=8002,
        ),
    )

    # launch it
    server_task = asyncio.create_task(workflow_service.launch_server())

    # process run task
    task = TaskDefinition(
        task_id="1",
        input=json.dumps({}),
        session_id="test_session_id",
    )

    await workflow_service.process_message(
        QueueMessage(
            action=ActionTypes.NEW_TASK,
            data=task.model_dump(),
        )
    )

    # process human response event task
    serializer = JsonSerializer()
    ev = HumanResponseEvent(response="42")
    task = TaskDefinition(
        task_id="1",
        session_id="test_session_id",
        input=serializer.serialize(ev),
    )
    await workflow_service.process_message(
        QueueMessage(
            action=ActionTypes.SEND_EVENT,
            data=task.model_dump(),
        )
    )

    # give time to process and shutdown afterwards
    await asyncio.sleep(1)
    consumer_task.cancel()
    server_task.cancel()

    # assert
    result = human_output_consumer.processed_messages[-1]
    assert result.action == ActionTypes.COMPLETED_TASK
    assert result.data["result"] == "42"

    # allow a clean shutdown
    await asyncio.gather(consumer_task, server_task, return_exceptions=True)


def test_defaults(
    test_workflow: Workflow,
) -> None:
    workflow_service = WorkflowService(
        test_workflow,
        None,  # type: ignore
        config=WorkflowServiceConfig(
            service_name="test_workflow",
            description="Test Workflow Service",
            host="localhost",
            port=8001,
        ),
    )
    assert workflow_service.publisher_id.startswith("WorkflowService-")
    assert workflow_service.publish_callback is None
    sd = workflow_service.service_definition
    assert sd.service_name == "test_workflow"
