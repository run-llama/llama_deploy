import pytest
from typing import List
from agentfile.services import ToolService
from agentfile.message_queues.simple import SimpleMessageQueue
from llama_index.core.tools import FunctionTool, BaseTool


@pytest.fixture()
def tools() -> List[BaseTool]:
    def multiply(a: int, b: int) -> int:
        """Multiple two integers and returns the result integer"""
        return a * b

    return [FunctionTool.from_defaults(fn=multiply)]


@pytest.mark.asyncio()
async def test_init(tools: List[BaseTool]) -> None:
    # arange
    server = ToolService(
        SimpleMessageQueue(),
        tools=tools,
        running=False,
        description="Test Tool Server",
        step_interval=0.5,
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
