from llama_index.core.agent import ReActAgent
from llama_index.core.llms import MockLLM

from llama_deploy.message_queues.simple import SimpleMessageQueueServer
from llama_deploy.services import AgentService


def test_init() -> None:
    agent = ReActAgent.from_tools([], llm=MockLLM())
    server = AgentService(
        agent,
        SimpleMessageQueueServer(),  # type:ignore
        running=False,
        description="Test Agent Server",
        step_interval=0.5,
        host="localhost",
        port=8001,
    )

    assert server.agent == agent
    assert server.running is False
    assert server.description == "Test Agent Server"
    assert server.step_interval == 0.5
