import pytest

from llama_index.core.llms import MockLLM
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool, ToolMetadata

from llama_agents.message_queues.simple import SimpleMessageQueue
from llama_agents.services.agent import AgentService
from llama_agents.tools.agent_service_tool import AgentServiceTool


@pytest.fixture()
def agent_service() -> AgentService:
    # create an agent
    def get_the_secret_fact() -> str:
        """Returns the secret fact."""
        return "The secret fact is: A baby llama is called a 'Cria'."

    tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

    agent = ReActAgent.from_tools([tool], llm=MockLLM(max_tokens=2))
    return AgentService(
        agent,
        SimpleMessageQueue(),
        running=False,
        description="Test Agent Server",
        step_interval=0.5,
        host="https://mock-agent-service.io",
        port=8000,
    )


@pytest.fixture()
def message_queue() -> SimpleMessageQueue:
    return SimpleMessageQueue()


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


@pytest.mark.asyncio()
async def test_tool_call_output(
    message_queue: SimpleMessageQueue, agent_service: AgentService
) -> None:
    pass


@pytest.mark.asyncio()
async def test_tool_call_raise_timeout(
    message_queue: SimpleMessageQueue, agent_service: AgentService
) -> None:
    ...


@pytest.mark.asyncio()
async def test_tool_call_hits_timeout_returns_tool_output(
    message_queue: SimpleMessageQueue, agent_service: AgentService
) -> None:
    ...
