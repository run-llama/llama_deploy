import asyncio
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest
from pydantic import PrivateAttr, ValidationError

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.simple import SimpleMessageQueue
from llama_deploy.messages.base import QueueMessage
from llama_deploy.services import HumanService
from llama_deploy.services.human import HELP_REQUEST_TEMPLATE_STR
from llama_deploy.types import (
    CONTROL_PLANE_NAME,
    ActionTypes,
    ChatMessage,
    TaskDefinition,
)


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.fixture()
def human_output_consumer() -> MockMessageConsumer:
    return MockMessageConsumer(message_type=CONTROL_PLANE_NAME)


@pytest.mark.asyncio()
async def test_init() -> None:
    # arrange
    # act
    human_service = HumanService(
        message_queue=SimpleMessageQueue(),  # type:ignore
        running=False,
        description="Test Human Service",
        service_name="Test Human Service",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )

    # assert
    assert not human_service.running
    assert human_service.description == "Test Human Service"
    assert human_service.service_name == "Test Human Service"
    assert human_service.step_interval == 0.5


def test_invalid_human_prompt_raises_validation_error() -> None:
    # arrange
    invalid_human_prompt_input_str = "{incorrect_param}"
    human_service = HumanService(
        message_queue=SimpleMessageQueue(),  # type: ignore
        host="localhost",
        port=8001,
    )

    # act/assert
    with pytest.raises(ValidationError):
        # using invalid prompt at construction should fail
        _ = HumanService(
            human_input_prompt=invalid_human_prompt_input_str,
            message_queue=SimpleMessageQueue(),  # type: ignore
        )
    with pytest.raises(ValueError):
        # updating prompt should fail
        human_service.human_input_prompt = invalid_human_prompt_input_str


@pytest.mark.asyncio()
@patch("llama_deploy.types.core.uuid")
async def test_create_task(mock_uuid: MagicMock) -> None:
    # arrange
    human_service = HumanService(
        message_queue=SimpleMessageQueue(),  # type: ignore
        running=False,
        description="Test Human Service",
        service_name="Test Human Service",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )
    mock_uuid.uuid4.return_value = "mock_id"
    task = TaskDefinition(task_id="1", input="Mock human req.")

    # act
    result = await human_service.create_task(task)

    # assert
    assert result == {"task_id": task.task_id}
    assert human_service._outstanding_human_tasks[0].task_def == task


@pytest.mark.asyncio()
@patch("builtins.input")
async def test_process_task(
    mock_input: MagicMock,
    human_output_consumer: MockMessageConsumer,
    message_queue_server: Any,
) -> None:
    # arrange
    mq = SimpleMessageQueue()
    human_service = HumanService(
        message_queue=mq,  # type: ignore
        host="localhost",
        port=8001,
    )

    consumer_fn = await mq.register_consumer(
        human_output_consumer, topic="llama_deploy.control_plane"
    )
    consumer_task = asyncio.create_task(consumer_fn())
    service_task = asyncio.create_task(human_service.processing_loop())
    await asyncio.sleep(0.5)
    mock_input.return_value = "Test human input."

    # act
    req = TaskDefinition(task_id="1", input="Mock human req.")
    result = await human_service.create_task(req)
    await asyncio.sleep(0.5)

    # tear down
    consumer_task.cancel()
    service_task.cancel()
    await asyncio.gather(consumer_task, service_task)

    # assert
    mock_input.assert_called_once()
    mock_input.assert_called_with(
        HELP_REQUEST_TEMPLATE_STR.format(input_str="Mock human req.")
    )
    assert len(human_output_consumer.processed_messages) == 1
    assert (
        human_output_consumer.processed_messages[0].data.get("result")
        == "Test human input."
    )
    assert human_output_consumer.processed_messages[0].data.get("task_id") == "1"
    assert result == {"task_id": req.task_id}
    assert len(human_service._outstanding_human_tasks) == 0


@pytest.mark.asyncio()
@patch("builtins.input")
async def test_process_human_req_from_queue(
    mock_input: MagicMock,
    human_output_consumer: MockMessageConsumer,
    message_queue_server: Any,
) -> None:
    # arrange
    mq = SimpleMessageQueue()
    human_service = HumanService(
        message_queue=mq,  # type: ignore
        service_name="test_human_service",
        host="localhost",
        port=8001,
    )

    consumer_fn = await mq.register_consumer(
        human_output_consumer, topic="llama_deploy.control_plane"
    )
    consumer_task = asyncio.create_task(consumer_fn())

    service_task = asyncio.create_task(human_service.processing_loop())
    service_consumer_fn = await mq.register_consumer(
        human_service.as_consumer(), topic="test_human_service"
    )
    service_consumer_task = asyncio.create_task(service_consumer_fn())
    await asyncio.sleep(0.5)
    mock_input.return_value = "Test human input."

    # act
    req = TaskDefinition(task_id="1", input="Mock human req.")
    human_req_message = QueueMessage(
        data=req.model_dump(),
        action=ActionTypes.NEW_TASK,
        type="test_human_service",
    )
    await mq.publish(human_req_message, topic="test_human_service")
    await asyncio.sleep(0.5)

    # tear down
    consumer_task.cancel()
    service_task.cancel()
    service_consumer_task.cancel()
    await asyncio.gather(consumer_task, service_task, service_consumer_task)

    # assert
    assert human_service.message_queue == mq
    assert len(human_output_consumer.processed_messages) == 1
    assert (
        human_output_consumer.processed_messages[0].data.get("result")
        == "Test human input."
    )
    assert human_output_consumer.processed_messages[0].data.get("task_id") == "1"
    assert len(human_service._outstanding_human_tasks) == 0


@pytest.mark.asyncio()
async def test_process_task_with_custom_human_input_fn(
    human_output_consumer: MockMessageConsumer, message_queue_server: Any
) -> None:
    # arrange
    mq = SimpleMessageQueue()

    async def my_custom_human_input_fn(prompt: str, task_id: str, **kwargs: Any) -> str:
        return " ".join([prompt, prompt[::-1]])

    human_service = HumanService(
        message_queue=mq,  # type:ignore
        fn_input=my_custom_human_input_fn,
        human_input_prompt="{input_str}",
        host="localhost",
        port=8001,
    )

    consumer_fn = await mq.register_consumer(
        human_output_consumer, topic="llama_deploy.control_plane"
    )
    consumer_task = asyncio.create_task(consumer_fn())
    service_task = asyncio.create_task(human_service.processing_loop())
    await asyncio.sleep(0.5)

    # act
    req = TaskDefinition(task_id="1", input="Mock human req.")
    result = await human_service.create_task(req)
    await asyncio.sleep(0.5)

    # tear down
    consumer_task.cancel()
    service_task.cancel()
    await asyncio.gather(consumer_task, service_task)

    # assert
    assert len(human_output_consumer.processed_messages) == 1
    assert (
        human_output_consumer.processed_messages[0].data.get("result")
        == "Mock human req. .qer namuh kcoM"
    )
    assert human_output_consumer.processed_messages[0].data.get("task_id") == "1"
    assert result == {"task_id": req.task_id}
    assert len(human_service._outstanding_human_tasks) == 0


@pytest.mark.asyncio()
@patch("builtins.input")
async def test_process_task_as_tool_call(
    mock_input: MagicMock,
    message_queue_server: Any,
) -> None:
    # arrange
    mq = SimpleMessageQueue()
    human_service = HumanService(
        message_queue=mq,  # type: ignore
        service_name="test_human_service",
        host="localhost",
        port=8001,
    )
    output_consumer = MockMessageConsumer(message_type="tool_call_source")
    consumer_fn = await mq.register_consumer(
        output_consumer, topic="llama_deploy.tool_call_source"
    )
    consumer_task = asyncio.create_task(consumer_fn())

    service_task = asyncio.create_task(human_service.processing_loop())
    service_consumer_fn = await mq.register_consumer(
        human_service.as_consumer(), topic="test_human_service"
    )
    service_consumer_task = asyncio.create_task(service_consumer_fn())
    await asyncio.sleep(0.5)

    mock_input.return_value = "Test human input."

    # act
    req = TaskDefinition(task_id="1", input="Mock human req.")
    human_req_message = QueueMessage(
        publisher_id="tool_call_source",
        data=req.model_dump(),
        action=ActionTypes.NEW_TOOL_CALL,
        type="test_human_service",
    )
    await mq.publish(human_req_message, topic="test_human_service")
    await asyncio.sleep(0.5)

    # tear down
    consumer_task.cancel()
    service_task.cancel()
    service_consumer_task.cancel()
    await asyncio.gather(consumer_task, service_task, service_consumer_task)

    # assert
    assert human_service.tool_name == "test_human_service-as-tool"
    assert len(output_consumer.processed_messages) == 1
    assert (
        output_consumer.processed_messages[0].data.get("result") == "Test human input."
    )
    try:
        tool_message = ChatMessage.model_validate(
            output_consumer.processed_messages[0].data.get("tool_message")
        )
        assert tool_message.role == "tool"
    except ValidationError:
        pytest.fail("Unable to parse result into a ChatMessage object.")
    assert output_consumer.processed_messages[0].data.get("id_") == "1"
    assert len(human_service._outstanding_human_tasks) == 0
