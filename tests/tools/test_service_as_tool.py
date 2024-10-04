import pytest

from llama_deploy.message_queues.simple import SimpleMessageQueue
from llama_deploy.services.human import HumanService
from llama_deploy.services.agent import AgentService
from llama_deploy.tools.service_as_tool import ServiceAsTool

from llama_index.core.agent import ReActAgent
from llama_index.core.llms import MockLLM
from llama_index.core.tools import FunctionTool, ToolMetadata


@pytest.fixture()
def message_queue() -> SimpleMessageQueue:
    return SimpleMessageQueue()


@pytest.fixture()
def human_service(message_queue: SimpleMessageQueue) -> HumanService:
    return HumanService(
        message_queue=message_queue,
        running=False,
        description="Test Human Service",
        service_name="test_human_service",
        host="https://mock-human-service.io",
        port=8000,
    )


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


@pytest.mark.parametrize(
    ("service_type"),
    ["human_service", "agent_service"],
)
def test_init(
    message_queue: SimpleMessageQueue,
    service_type: str,
    request: pytest.FixtureRequest,
) -> None:
    # arrange
    service = request.getfixturevalue(service_type)
    tool_metadata = ToolMetadata(
        description=service.description,
        name=service.tool_name,
    )
    # act
    agent_service_tool = ServiceAsTool(
        tool_metadata=tool_metadata,
        message_queue=message_queue,
        service_name=service.service_name,
        timeout=5.5,
        step_interval=0.5,
    )

    # assert
    assert agent_service_tool.step_interval == 0.5
    assert agent_service_tool.message_queue == message_queue
    assert agent_service_tool.metadata == tool_metadata
    assert agent_service_tool.timeout == 5.5
    assert agent_service_tool.service_name == service.service_name
    assert agent_service_tool.registered is False


@pytest.mark.parametrize(
    ("service_type"),
    ["human_service", "agent_service"],
)
def test_init_invalid_tool_name_should_raise_error(
    message_queue: SimpleMessageQueue,
    service_type: str,
    request: pytest.FixtureRequest,
) -> None:
    # arrange
    service = request.getfixturevalue(service_type)
    tool_metadata = ToolMetadata(
        description=service.description,
        name="incorrect-name",
    )
    # act/assert
    with pytest.raises(ValueError):
        ServiceAsTool(
            tool_metadata=tool_metadata,
            message_queue=message_queue,
            service_name=service.service_name,
        )


@pytest.mark.parametrize(
    ("service_type"),
    ["human_service", "agent_service"],
)
def test_from_service_definition(
    message_queue: SimpleMessageQueue,
    service_type: str,
    request: pytest.FixtureRequest,
) -> None:
    # arrange
    service = request.getfixturevalue(service_type)
    service_def = service.service_definition

    # act
    agent_service_tool = ServiceAsTool.from_service_definition(
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
    assert agent_service_tool.service_name == service.service_name
    assert agent_service_tool.raise_timeout is True
    assert agent_service_tool.registered is False
