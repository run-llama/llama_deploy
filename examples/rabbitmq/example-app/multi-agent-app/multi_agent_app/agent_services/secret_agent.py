import asyncio

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
message_queue = RabbitMQMessageQueue(
    url=f"amqp://{message_queue_username}:{message_queue_password}@{message_queue_host}:{message_queue_port}/"
)

agent_server = AgentService(
    agent=agent,
    message_queue=message_queue,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
    host=secret_agent_host,
    port=int(secret_agent_port) if secret_agent_port else None,
)

app = agent_server._app


# registration
async def register_and_start_consuming() -> None:
    # register to message queue
    start_consuming_callable = await agent_server.register_to_message_queue()
    # register to control plane
    await agent_server.register_to_control_plane(
        control_plane_url=(
            f"http://{control_plane_host}:{control_plane_port}"
            if control_plane_port
            else f"http://{control_plane_host}"
        )
    )
    # start consuming
    await start_consuming_callable()


if __name__ == "__main__":
    asyncio.run(register_and_start_consuming())
