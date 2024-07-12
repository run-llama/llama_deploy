import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from llama_index.core.llms import MockLLM
from llama_index.core.agent import ReActAgent, AgentChatResponse
from llama_index.core.agent.types import TaskStepOutput, TaskStep, Task
from llama_index.core.tools import FunctionTool
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


@pytest.fixture()
def task_step_output() -> TaskStepOutput:
    return TaskStepOutput(
        output=AgentChatResponse(response="A baby llama is called a 'Cria'."),
        task_step=TaskStep(task_id="", step_id=""),
        next_steps=[],
        is_last=True,
    )


@pytest.fixture()
def completed_task() -> Task:
    return Task(
        task_id="",
        input="What is the secret fact?",
        memory=ChatMemoryBuffer.from_defaults(),
    )


@pytest.mark.asyncio()
@patch.object(ReActAgent, "arun_step")
@patch.object(ReActAgent, "get_completed_tasks")
async def test_tool_call_output(
    mock_get_completed_tasks: MagicMock,
    mock_arun_step: AsyncMock,
    message_queue: SimpleMessageQueue,
    agent_service: AgentService,
    task_step_output: TaskStepOutput,
    completed_task: Task,
) -> None:
    # arrange
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
async def test_tool_call_raises_timeout_error(
    mock_get_completed_tasks: MagicMock,
    mock_arun_step: AsyncMock,
    message_queue: SimpleMessageQueue,
    agent_service: AgentService,
    task_step_output: TaskStepOutput,
    completed_task: Task,
) -> None:
    # arrange
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
@patch.object(ReActAgent, "arun_step")
@patch.object(ReActAgent, "get_completed_tasks")
async def test_tool_call_hits_timeout_but_returns_tool_output(
    mock_get_completed_tasks: MagicMock,
    mock_arun_step: AsyncMock,
    message_queue: SimpleMessageQueue,
    agent_service: AgentService,
    task_step_output: TaskStepOutput,
    completed_task: Task,
) -> None:
    # arrange
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
        raise_timeout=False,
    )

    # startup
    await message_queue.register_consumer(agent_service.as_consumer())
    mq_task = asyncio.create_task(message_queue.processing_loop())
    as_task = asyncio.create_task(agent_service.processing_loop())

    # act/assert
    tool_output = await agent_service_tool.acall(input="What is the secret fact?")

    # clean-up/shutdown
    mq_task.cancel()
    as_task.cancel()

    assert "Encountered error" in tool_output.content
    assert tool_output.is_error
    assert tool_output.tool_name == agent_service_tool.metadata.name
    assert tool_output.raw_input == {
        "args": (),
        "kwargs": {"input": "What is the secret fact?"},
    }
    assert len(agent_service_tool.tool_call_results) == 0
    assert agent_service_tool.registered is True
