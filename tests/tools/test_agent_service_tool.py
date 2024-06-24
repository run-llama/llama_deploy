import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from llama_index.core.llms import MockLLM
from llama_index.core.agent import ReActAgent, AgentChatResponse
from llama_index.core.agent.types import TaskStepOutput, TaskStep, Task
from llama_index.core.tools import FunctionTool, ToolMetadata
from llama_index.core.memory import ChatMemoryBuffer

from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.services.agent import AgentService
from llama_agents.tools.agent_service_tool import AgentServiceTool


@pytest.fixture()
def message_queue() -> SimpleMessageQueue:
    return SimpleMessageQueue()


@pytest.fixture()
def agent_service(message_queue: SimpleMessageQueue) -> AgentService:
    # create an agent
    def get_the_secret_fact() -> str:
        """Returns the secret fact."""
        return "The secret fact is: A baby llama is called a 'Cria'."

    tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

    agent = ReActAgent.from_tools([tool], llm=MockLLM())
    return AgentService(
        agent,
        message_queue=message_queue,
        description="Test Agent Server",
        host="https://mock-agent-service.io",
        port=8000,
    )


def test_init(message_queue: SimpleMessageQueue, agent_service: AgentService) -> None:
    # arrange
    tool_metadata = ToolMetadata(
        description=agent_service.description,
        name=f"{agent_service.service_name}-as-tool",
    )
    # act
    agent_service_tool = AgentServiceTool(
        tool_metadata=tool_metadata,
        message_queue=message_queue,
        service_name=agent_service.service_name,
        timeout=5.5,
        step_interval=0.5,
    )

    # assert
    assert agent_service_tool.step_interval == 0.5
    assert agent_service_tool.message_queue == message_queue
    assert agent_service_tool.metadata == tool_metadata
    assert agent_service_tool.timeout == 5.5
    assert agent_service_tool.service_name == agent_service.service_name
    assert agent_service_tool.registered is False


def test_from_service_definition(
    message_queue: SimpleMessageQueue, agent_service: AgentService
) -> None:
    # arrange
    service_def = agent_service.service_definition

    # act
    agent_service_tool = AgentServiceTool.from_service_definition(
        message_queue=message_queue,
        service_definition=service_def,
        timeout=5.5,
        step_interval=0.5,
        raise_timeout=True,
    )

    # assert
    assert agent_service_tool.step_interval == 0.5
    assert agent_service_tool.message_queue == message_queue
    assert agent_service_tool.metadata.description == service_def.description
    assert agent_service_tool.metadata.name == f"{service_def.service_name}-as-tool"
    assert agent_service_tool.timeout == 5.5
    assert agent_service_tool.service_name == agent_service.service_name
    assert agent_service_tool.raise_timeout is True
    assert agent_service_tool.registered is False


@pytest.mark.asyncio()
@patch.object(ReActAgent, "arun_step")
@patch.object(ReActAgent, "get_completed_tasks")
async def test_tool_call_output(
    mock_get_completed_tasks: MagicMock,
    mock_arun_step: AsyncMock,
    message_queue: SimpleMessageQueue,
    agent_service: AgentService,
) -> None:
    # arrange
    task_step_output = TaskStepOutput(
        output=AgentChatResponse(response="A baby llama is called a 'Cria'."),
        task_step=TaskStep(task_id="", step_id=""),
        next_steps=[],
        is_last=True,
    )
    completed_task = Task(
        task_id="",
        input="What is the secret fact?",
        memory=ChatMemoryBuffer.from_defaults(),
    )

    def arun_side_effect(task_id: str) -> TaskStepOutput:
        completed_task.task_id = task_id
        task_step_output.task_step.task_id = task_id
        return task_step_output

    mock_arun_step.side_effect = arun_side_effect
    mock_get_completed_tasks.side_effect = [
        [],
        [],
        [completed_task],
        [completed_task],
        [completed_task],
    ]

    agent_service_tool = AgentServiceTool.from_service_definition(
        message_queue=message_queue,
        service_definition=agent_service.service_definition,
    )

    # startup
    await message_queue.register_consumer(agent_service.as_consumer())
    mq_task = asyncio.create_task(message_queue.processing_loop())
    as_task = asyncio.create_task(agent_service.processing_loop())

    # act
    tool_output = await agent_service_tool.acall(input="What is the secret fact?")

    # clean-up/shutdown
    await asyncio.sleep(0.1)
    mq_task.cancel()
    as_task.cancel()

    # assert
    assert tool_output.content == "A baby llama is called a 'Cria'."
    assert tool_output.tool_name == agent_service_tool.metadata.name
    assert tool_output.raw_input == {
        "args": (),
        "kwargs": {"input": "What is the secret fact?"},
    }
    assert len(agent_service_tool.tool_call_results) == 0
    assert agent_service_tool.registered is True


@pytest.mark.asyncio()
@patch.object(ReActAgent, "arun_step")
@patch.object(ReActAgent, "get_completed_tasks")
async def test_tool_call_raise_timeout(
    mock_get_completed_tasks: MagicMock,
    mock_arun_step: AsyncMock,
    message_queue: SimpleMessageQueue,
    agent_service: AgentService,
) -> None:
    # arrange
    task_step_output = TaskStepOutput(
        output=AgentChatResponse(response="A baby llama is called a 'Cria'."),
        task_step=TaskStep(task_id="", step_id=""),
        next_steps=[],
        is_last=True,
    )
    completed_task = Task(
        task_id="",
        input="What is the secret fact?",
        memory=ChatMemoryBuffer.from_defaults(),
    )

    def arun_side_effect(task_id: str) -> TaskStepOutput:
        completed_task.task_id = task_id
        task_step_output.task_step.task_id = task_id
        return task_step_output

    mock_arun_step.side_effect = arun_side_effect
    mock_get_completed_tasks.side_effect = [
        [],
        [],
        [completed_task],
        [completed_task],
        [completed_task],
    ]

    agent_service_tool = AgentServiceTool.from_service_definition(
        message_queue=message_queue,
        service_definition=agent_service.service_definition,
        timeout=1e-12,
        raise_timeout=True,
    )

    # startup
    await message_queue.register_consumer(agent_service.as_consumer())
    mq_task = asyncio.create_task(message_queue.processing_loop())
    as_task = asyncio.create_task(agent_service.processing_loop())

    # act/assert
    with pytest.raises(
        (TimeoutError, asyncio.TimeoutError, asyncio.exceptions.TimeoutError)
    ):
        await agent_service_tool.acall(input="What is the secret fact?")

    # clean-up/shutdown
    mq_task.cancel()
    as_task.cancel()


@pytest.mark.asyncio()
async def test_tool_call_hits_timeout_returns_tool_output(
    message_queue: SimpleMessageQueue, agent_service: AgentService
) -> None:
    ...
