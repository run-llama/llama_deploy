import asyncio
from pydantic import PrivateAttr
import pytest
from typing import Any, List


from llama_index.core.tools import FunctionTool, BaseTool

from llama_deploy.services import ToolService
from llama_deploy.message_queues.simple import SimpleMessageQueue
from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.messages.base import QueueMessage
from llama_deploy.types import ToolCall, ToolCallBundle, ActionTypes

TOOL_CALL_SOURCE = "mock-source"


class MockMessageConsumer(BaseMessageQueueConsumer):
    processed_messages: List[QueueMessage] = []
    _lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)

    async def _process_message(self, message: QueueMessage, **kwargs: Any) -> None:
        async with self._lock:
            self.processed_messages.append(message)


@pytest.fixture()
def tools() -> List[BaseTool]:
    def multiply(a: int, b: int) -> int:
        """Multiple two integers and returns the result integer"""
        return a * b

    return [FunctionTool.from_defaults(fn=multiply)]


@pytest.fixture()
def tool_call() -> ToolCall:
    tool_bundle = ToolCallBundle(
        tool_name="multiply", tool_args=[], tool_kwargs={"a": 1, "b": 2}
    )
    return ToolCall(tool_call_bundle=tool_bundle, source_id=TOOL_CALL_SOURCE)


@pytest.fixture()
def tool_output_consumer() -> MockMessageConsumer:
    return MockMessageConsumer(message_type=TOOL_CALL_SOURCE)


@pytest.mark.asyncio()
async def test_init(tools: List[BaseTool]) -> None:
    # arrange
    server = ToolService(
        SimpleMessageQueue(),
        tools=tools,
        running=False,
        description="Test Tool Server",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )

    # act
    result = await server.get_tool_by_name("multiply")
    multiply_tool_metadata = result["tool_metadata"]

    # assert
    assert server.tools == tools
    assert multiply_tool_metadata == tools[0].metadata
    assert server.running is False
    assert server.description == "Test Tool Server"
    assert server.step_interval == 0.5


@pytest.mark.asyncio()
async def test_create_tool_call(tools: List[BaseTool], tool_call: ToolCall) -> None:
    # arrange
    server = ToolService(
        SimpleMessageQueue(),
        tools=tools,
        running=False,
        description="Test Tool Server",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )

    # act
    result = await server.create_tool_call(tool_call)

    # assert
    assert result == {"tool_call_id": tool_call.id_}
    assert server._outstanding_tool_calls[tool_call.id_] == tool_call


@pytest.mark.asyncio()
async def test_process_tool_call(
    tools: List[BaseTool],
    tool_call: ToolCall,
    tool_output_consumer: MockMessageConsumer,
) -> None:
    # arrange
    mq = SimpleMessageQueue()
    server = ToolService(
        mq,
        tools=tools,
        running=True,
        description="Test Tool Server",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )
    await mq.register_consumer(tool_output_consumer)

    mq_task = await mq.launch_local()
    server_task = await server.launch_local()

    # act
    result = await server.create_tool_call(tool_call)

    # Give some time for last message to get published and sent to consumers
    await asyncio.sleep(1)
    mq_task.cancel()
    server_task.cancel()

    # assert
    assert server.message_queue == mq
    assert result == {"tool_call_id": tool_call.id_}
    assert len(tool_output_consumer.processed_messages) == 1
    assert tool_output_consumer.processed_messages[0].data.get("result") == "2"


@pytest.mark.asyncio()
async def test_process_tool_call_from_queue(
    tools: List[BaseTool],
    tool_call: ToolCall,
    tool_output_consumer: MockMessageConsumer,
) -> None:
    # arrange
    mq = SimpleMessageQueue()
    server = ToolService(
        mq,
        tools=tools,
        running=True,
        service_name="test_tool_service",
        description="Test Tool Server",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )
    await mq.register_consumer(tool_output_consumer)
    await mq.register_consumer(server.as_consumer())

    mq_task = await mq.launch_local()
    server_task = await server.launch_local()

    # act
    tool_call_message = QueueMessage(
        data=tool_call.model_dump(),
        action=ActionTypes.NEW_TOOL_CALL,
        type="test_tool_service",
    )
    await mq.publish(tool_call_message)

    # Give some time for last message to get published and sent to consumers
    await asyncio.sleep(1)
    mq_task.cancel()
    server_task.cancel()

    # assert
    assert server.message_queue == mq
    assert len(tool_output_consumer.processed_messages) == 1
    assert tool_output_consumer.processed_messages[0].data.get("result") == "2"
