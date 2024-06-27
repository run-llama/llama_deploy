import asyncio

from llama_agents import AgentOrchestrator, ControlPlaneServer, SimpleMessageQueue
from llama_index.llms.openai import OpenAI

from multi_agent_app.utils import load_from_env


message_queue_host = load_from_env("MESSAGE_QUEUE_HOST")
message_queue_port = int(load_from_env("MESSAGE_QUEUE_PORT"))
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = int(load_from_env("CONTROL_PLANE_PORT"))


# setup message queue
message_queue = SimpleMessageQueue(host=message_queue_host, port=message_queue_port)
queue_client = message_queue.client

# setup control plane
control_plane = ControlPlaneServer(
    message_queue=queue_client,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
    host=control_plane_host,
    port=control_plane_port,
)


app = control_plane.app


async def register() -> None:
    # register to message queue
    await queue_client.register_consumer(control_plane.as_consumer(remote=True))


if __name__ == "__main__":
    asyncio.run(register())
