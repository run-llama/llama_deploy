from llama_index.core.llms import MockLLM
from llama_index.core.agent import ReActAgent

from agentfile.agent import AgentServer


def test_init() -> None:
    agent = ReActAgent.from_tools([], llm=MockLLM())
    server = AgentServer(
        agent, running=False, description="Test Agent Server", step_interval=0.5
    )

    assert server.agent == agent
    assert server.running is False
    assert server.description == "Test Agent Server"
    assert server.step_interval == 0.5
