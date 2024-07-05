import asyncio
import uvicorn

from llama_agents import AgentService
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

from multi_agent_app.utils import load_from_env


message_queue_host = load_from_env("RABBITMQ_HOST")
message_queue_port = load_from_env("RABBITMQ_NODE_PORT")
message_queue_username = load_from_env("RABBITMQ_DEFAULT_USER")
message_queue_password = load_from_env("RABBITMQ_DEFAULT_PASS")
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")
funny_agent_host = load_from_env("FUNNY_AGENT_HOST")
funny_agent_port = load_from_env("FUNNY_AGENT_PORT")
localhost = load_from_env("LOCALHOST")


# create an agent
def get_a_funny_joke() -> str:
    """Returns the secret fact."""
    return "I went to the aquarium this weekend, but I didn’t stay long. There’s something fishy about that place."


tool = FunctionTool.from_defaults(fn=get_a_funny_joke)
worker = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
agent = worker.as_agent()

# create agent server
message_queue = RabbitMQMessageQueue(
    url=f"amqp://{message_queue_username}:{message_queue_password}@{message_queue_host}:{message_queue_port}/"
)

agent_server = AgentService(
    agent=agent,
    message_queue=message_queue,
    description="Useful for getting funny jokes.",
    service_name="funny_joke_agent",
    host=funny_agent_host,
    port=int(funny_agent_port) if funny_agent_port else None,
)

app = agent_server._app


# launch
async def launch() -> None:
    # register to message queue
    start_consuming_callable = await agent_server.register_to_message_queue()
    _ = asyncio.create_task(start_consuming_callable())

    # register to control plane
    await agent_server.register_to_control_plane(
        control_plane_url=(
            f"http://{control_plane_host}:{control_plane_port}"
            if control_plane_port
            else f"http://{control_plane_host}"
        )
    )

    cfg = uvicorn.Config(
        agent_server._app,
        host=localhost,
        port=agent_server.port,
    )
    server = uvicorn.Server(cfg)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(launch())
