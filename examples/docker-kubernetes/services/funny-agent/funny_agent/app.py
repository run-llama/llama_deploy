import asyncio
import os

from llama_agents import AgentService, SimpleMessageQueue

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

try:
    message_queue_host = os.environ["MESSAGE_QUEUE_HOST"]
except KeyError:
    raise ValueError("Missing env var `MESSAGE_QUEUE_HOST`.")

try:
    funny_agent_host = os.environ["FUNNY_AGENT_HOST"]
except KeyError:
    raise ValueError("Missing env var `FUNNY_AGENT_HOST`.")


# create an agent
def get_a_funny_joke() -> str:
    """Returns the secret fact."""
    return "I went to the aquarium this weekend, but I didn’t stay long. There’s something fishy about that place."


tool = FunctionTool.from_defaults(fn=get_a_funny_joke)
worker = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
agent = worker.as_agent()

# create agent server
message_queue = SimpleMessageQueue(host=message_queue_host, port=8000)
queue_client = message_queue.client

agent_server = AgentService(
    agent=agent,
    message_queue=queue_client,
    description="Useful for getting funny jokes.",
    service_name="funny_joke_agent",
    host=funny_agent_host,
    port=8003,
)

app = agent_server._app


# registration
async def register() -> None:
    # register to message queue
    await agent_server.register_to_message_queue()
    # register to control plane
    await agent_server.register_to_control_plane(
        control_plane_url="http://0.0.0.0:8001"
    )


if __name__ == "__main__":
    asyncio.run(register())
