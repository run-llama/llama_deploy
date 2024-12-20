import asyncio
from typing import Any, Dict, List

import pytest
from llama_index.core.tools import BaseTool, FunctionTool
from pydantic import PrivateAttr

from llama_deploy.message_consumers.base import BaseMessageQueueConsumer
from llama_deploy.message_queues.simple import SimpleMessageQueueServer
from llama_deploy.messages.base import QueueMessage
from llama_deploy.services import ToolService
from llama_deploy.tools import MetaServiceTool

pytestmark = pytest.mark.skip


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
def message_queue() -> SimpleMessageQueueServer:
    return SimpleMessageQueueServer()


@pytest.fixture()
def tool_service(
    message_queue: SimpleMessageQueueServer, tools: List[BaseTool]
) -> ToolService:
    return ToolService(
        message_queue=message_queue,
        tools=tools,
        running=True,
        service_name="test_tool_service",
        description="Test Tool Server",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )


@pytest.mark.asyncio()
async def test_init(
    message_queue: SimpleMessageQueueServer,
    tools: List[BaseTool],
    tool_service: ToolService,
) -> None:
    # arrange
    result = await tool_service.get_tool_by_name("multiply")

    # act
    meta_service_tool = MetaServiceTool(
        tool_metadata=result["tool_metadata"],
        message_queue=message_queue,
        tool_service_name=tool_service.service_name,
    )

    # assert
    assert meta_service_tool.metadata.name == "multiply"
    assert not meta_service_tool.registered


@pytest.mark.asyncio()
async def test_create_from_tool_service_direct(
    message_queue: SimpleMessageQueueServer, tool_service: ToolService
) -> None:
    # arrange

    # act
    meta_service_tool: MetaServiceTool = await MetaServiceTool.from_tool_service(
        tool_service=tool_service, message_queue=message_queue, name="multiply"
    )

    # assert
    assert meta_service_tool.metadata.name == "multiply"
    assert not meta_service_tool.registered


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    ("from_tool_service_kwargs"),
    [
        {"message_queue": SimpleMessageQueueServer(), "name": "multiply"},
        {
            "message_queue": SimpleMessageQueueServer(),
            "name": "multiply",
            "tool_service_name": "fake-name",
        },
        {
            "message_queue": SimpleMessageQueueServer(),
            "name": "multiply",
            "tool_service_api_key": "fake-key",
        },
        {
            "message_queue": SimpleMessageQueueServer(),
            "name": "multiply",
            "tool_service_url": "fake-url",
        },
        {
            "message_queue": SimpleMessageQueueServer(),
            "name": "multiply",
            "tool_service_name": "fake-name",
            "tool_service_api_key": "fake-key",
        },
        {
            "message_queue": SimpleMessageQueueServer(),
            "name": "multiply",
            "tool_service_name": "fake-name",
            "tool_service_url": "fake-url",
        },
        {
            "message_queue": SimpleMessageQueueServer(),
            "name": "multiply",
            "tool_service_api_key": "fake-key",
            "tool_service_url": "fake-url",
        },
    ],
)
async def test_create_from_tool_service_raise_error(
    from_tool_service_kwargs: Dict[str, Any],
) -> None:
    # arrange
    # act/assert
    with pytest.raises(ValueError):
        await MetaServiceTool.from_tool_service(**from_tool_service_kwargs)


@pytest.mark.asyncio()
async def test_tool_call_output(
    message_queue: SimpleMessageQueueServer, tool_service: ToolService
) -> None:
    # arrange
    meta_service_tool: MetaServiceTool = await MetaServiceTool.from_tool_service(
        tool_service=tool_service, message_queue=message_queue, name="multiply"
    )
    await message_queue.register_consumer(tool_service.as_consumer())
    mq_task = await message_queue.launch_local()
    ts_task = asyncio.create_task(tool_service.processing_loop())

    # act
    tool_output = await meta_service_tool.acall(a=1, b=9)

    # clean-up/shutdown
    await asyncio.sleep(0.5)
    mq_task.cancel()
    ts_task.cancel()

    # assert
    assert tool_output.content == "9"
    assert tool_output.tool_name == "multiply"
    assert tool_output.raw_input == {"args": (), "kwargs": {"a": 1, "b": 9}}
    assert len(meta_service_tool.tool_call_results) == 0
    assert meta_service_tool.registered


@pytest.mark.asyncio()
async def test_tool_call_raise_timeout(
    message_queue: SimpleMessageQueueServer, tool_service: ToolService
) -> None:
    # arrange
    meta_service_tool: MetaServiceTool = await MetaServiceTool.from_tool_service(
        tool_service=tool_service,
        message_queue=message_queue,
        name="multiply",
        timeout=1e-9,
        raise_timeout=True,
    )
    await message_queue.register_consumer(tool_service.as_consumer())
    mq_task = await message_queue.launch_local()
    ts_task = asyncio.create_task(tool_service.processing_loop())

    # act/assert
    with pytest.raises(
        (TimeoutError, asyncio.TimeoutError, asyncio.exceptions.TimeoutError)
    ):
        await meta_service_tool.acall(a=1, b=9)

    mq_task.cancel()
    ts_task.cancel()


@pytest.mark.asyncio()
async def test_tool_call_reach_timeout(
    message_queue: SimpleMessageQueueServer, tool_service: ToolService
) -> None:
    # arrange
    meta_service_tool: MetaServiceTool = await MetaServiceTool.from_tool_service(
        tool_service=tool_service,
        message_queue=message_queue,
        name="multiply",
        timeout=1e-9,
        raise_timeout=False,
    )
    await message_queue.register_consumer(tool_service.as_consumer())
    mq_task = await message_queue.launch_local()
    ts_task = asyncio.create_task(tool_service.processing_loop())

    # act/assert
    tool_output = await meta_service_tool.acall(a=1, b=9)

    mq_task.cancel()
    ts_task.cancel()

    assert "Encountered error" in tool_output.content
    assert tool_output.tool_name == "multiply"
    assert tool_output.is_error
    assert tool_output.raw_input == {"args": (), "kwargs": {"a": 1, "b": 9}}
    assert len(meta_service_tool.tool_call_results) == 0
    assert meta_service_tool.registered
