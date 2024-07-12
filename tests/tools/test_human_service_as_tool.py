import asyncio
import pytest
import time
from unittest.mock import patch, MagicMock


from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.services.human import HumanService
from llama_agents.tools.service_as_tool import ServiceAsTool


@pytest.fixture()
def message_queue() -> SimpleMessageQueue:
    return SimpleMessageQueue()


@pytest.fixture()
def human_service(message_queue: SimpleMessageQueue) -> HumanService:
    return HumanService(
        message_queue=message_queue,
        description="Test Human Service",
        service_name="test_human_service",
        host="https://mock-human-service.io",
        port=8000,
    )


@pytest.mark.asyncio()
@patch("builtins.input")
async def test_tool_call_output(
    mock_input: MagicMock,
    message_queue: SimpleMessageQueue,
    human_service: HumanService,
) -> None:
    # arrange
    human_service_as_tool = ServiceAsTool.from_service_definition(
        message_queue=message_queue,
        service_definition=human_service.service_definition,
    )
    mock_input.return_value = "Test human input."

    # startup
    await message_queue.register_consumer(human_service.as_consumer())
    mq_task = asyncio.create_task(message_queue.processing_loop())
    hs_task = asyncio.create_task(human_service.processing_loop())

    # act
    tool_output = await human_service_as_tool.acall(input="Mock human request")

    # clean-up/shutdown
    await asyncio.sleep(0.1)
    mq_task.cancel()
    hs_task.cancel()

    # assert
    assert tool_output.content == "Test human input."
    assert tool_output.tool_name == human_service_as_tool.metadata.name
    assert tool_output.raw_input == {
        "args": (),
        "kwargs": {"input": "Mock human request"},
    }
    assert len(human_service_as_tool.tool_call_results) == 0
    assert human_service_as_tool.registered is True


@pytest.mark.asyncio()
@patch("builtins.input")
async def test_tool_call_raises_timeout_error(
    mock_input: MagicMock,
    message_queue: SimpleMessageQueue,
    human_service: HumanService,
) -> None:
    # arrange
    def input_side_effect(prompt: str) -> str:
        time.sleep(0.1)
        return prompt

    mock_input.side_effect = input_side_effect
    human_service_as_tool = ServiceAsTool.from_service_definition(
        message_queue=message_queue,
        service_definition=human_service.service_definition,
        timeout=1e-12,
        raise_timeout=True,
    )

    # startup
    await message_queue.register_consumer(human_service.as_consumer())
    mq_task = asyncio.create_task(message_queue.processing_loop())
    hs_task = asyncio.create_task(human_service.processing_loop())

    # act/assert
    with pytest.raises(
        (TimeoutError, asyncio.TimeoutError, asyncio.exceptions.TimeoutError)
    ):
        await human_service_as_tool.acall(input="Is this a mock request?")

    # clean-up/shutdown
    mq_task.cancel()
    hs_task.cancel()


@pytest.mark.asyncio()
@patch("builtins.input")
async def test_tool_call_hits_timeout_but_returns_tool_output(
    mock_input: MagicMock,
    message_queue: SimpleMessageQueue,
    human_service: HumanService,
) -> None:
    # arrange
    def input_side_effect(prompt: str) -> str:
        time.sleep(0.1)
        return prompt

    mock_input.side_effect = input_side_effect
    human_service_as_tool = ServiceAsTool.from_service_definition(
        message_queue=message_queue,
        service_definition=human_service.service_definition,
        timeout=1e-12,
        raise_timeout=False,
    )

    # startup
    await message_queue.register_consumer(human_service.as_consumer())
    mq_task = asyncio.create_task(message_queue.processing_loop())
    hs_task = asyncio.create_task(human_service.processing_loop())

    # act/assert
    tool_output = await human_service_as_tool.acall(input="Is this a mock request?")

    # clean-up/shutdown
    mq_task.cancel()
    hs_task.cancel()

    assert "Encountered error" in tool_output.content
    assert tool_output.is_error
    assert tool_output.tool_name == human_service_as_tool.metadata.name
    assert tool_output.raw_input == {
        "args": (),
        "kwargs": {"input": "Is this a mock request?"},
    }
    assert len(human_service_as_tool.tool_call_results) == 0
    assert human_service_as_tool.registered is True
