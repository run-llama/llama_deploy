from llama_index.core.llms import MockLLM
from llama_index.core.agent import ReActAgent

from llama_agents.services import AgentService
from llama_agents.message_queues.simple import SimpleMessageQueue


def test_init() -> None:
    agent = ReActAgent.from_tools([], llm=MockLLM())
    server = AgentService(
        agent,
        SimpleMessageQueue(),
        running=False,
        description="Test Agent Server",
        step_interval=0.5,
    )

    assert server.agent == agent
    assert server.running is False
    assert server.description == "Test Agent Server"
    assert server.step_interval == 0.5
