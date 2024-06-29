import asyncio

from llama_agents import AgentService, SimpleMessageQueue

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

from multi_agent_app.utils import load_from_env

message_queue_host = load_from_env("MESSAGE_QUEUE_HOST")
message_queue_port = load_from_env("MESSAGE_QUEUE_PORT")
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")
funny_agent_host = load_from_env("FUNNY_AGENT_HOST")
funny_agent_port = load_from_env("FUNNY_AGENT_PORT")


# create an agent
def get_a_funny_joke() -> str:
    """Returns the secret fact."""
    return "I went to the aquarium this weekend, but I didn’t stay long. There’s something fishy about that place."


tool = FunctionTool.from_defaults(fn=get_a_funny_joke)
worker = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
agent = worker.as_agent()

# create agent server
message_queue = SimpleMessageQueue(
    host=message_queue_host,
    port=int(message_queue_port) if message_queue_port else None,
)
queue_client = message_queue.client

agent_server = AgentService(
    agent=agent,
    message_queue=queue_client,
    description="Useful for getting funny jokes.",
    service_name="funny_joke_agent",
    host=funny_agent_host,
    port=int(funny_agent_port) if funny_agent_port else None,
)

app = agent_server._app


# registration
async def register() -> None:
    # register to message queue
    await agent_server.register_to_message_queue()
    # register to control plane
    await agent_server.register_to_control_plane(
        control_plane_url=(
            f"http://{control_plane_host}:{control_plane_port}"
            if control_plane_port
            else f"http://{control_plane_host}"
        )
    )


if __name__ == "__main__":
    asyncio.run(register())
