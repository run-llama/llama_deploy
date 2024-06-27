import asyncio

from llama_agents import AgentService, SimpleMessageQueue

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

from multi_agent_app.utils import load_from_env

message_queue_host = load_from_env("MESSAGE_QUEUE_HOST")
message_queue_port = load_from_env("MESSAGE_QUEUE_PORT")
secret_agent_host = load_from_env("SECRET_AGENT_HOST")
secret_agent_port = load_from_env("SECRET_AGENT_PORT")


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)
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
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
    host=secret_agent_host,
    port=int(secret_agent_port) if secret_agent_port else None,
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
