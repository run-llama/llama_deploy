from llama_index.core.llms import MockLLM
from llama_index.core.agent import ReActAgent

from agentfile.agent_server import FastAPIAgentServer
from agentfile.message_queues.simple import SimpleMessageQueue

from unittest.mock import patch, MagicMock


@patch("agentfile.agent_server.fastapi.uuid")
def test_init(mock_uuid: MagicMock) -> None:
    mock_uuid.uuid4.return_value = "mock"
    agent = ReActAgent.from_tools([], llm=MockLLM())
    mq = SimpleMessageQueue()
    server = FastAPIAgentServer(
        agent,
        mq,
        running=False,
        description="Test Agent Server",
        step_interval=0.5,
    )

    assert server.agent == agent
    assert server.running is False
    assert server.description == "Test Agent Server"
    assert server.step_interval == 0.5
    assert server.message_queue == mq
    assert server.publisher_id == "FastAPIAgentServer-mock"
