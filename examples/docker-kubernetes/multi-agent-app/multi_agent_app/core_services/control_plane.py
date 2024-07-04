import asyncio

from llama_agents import AgentOrchestrator, ControlPlaneServer, SimpleMessageQueue
from llama_index.llms.openai import OpenAI

from multi_agent_app.utils import load_from_env


message_queue_host = load_from_env("MESSAGE_QUEUE_HOST")
message_queue_port = load_from_env("MESSAGE_QUEUE_PORT")
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")


# setup message queue
message_queue = SimpleMessageQueue(
    host=message_queue_host,
    port=int(message_queue_port) if message_queue_port else None,
)
queue_client = message_queue.client

# setup control plane
control_plane = ControlPlaneServer(
    message_queue=queue_client,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
    host=control_plane_host,
    port=int(control_plane_port) if control_plane_port else None,
)


app = control_plane.app


async def register_and_start_consuming() -> None:
    # register to message queue
    start_consuming_callable = await control_plane.register_to_message_queue()
    await start_consuming_callable()


if __name__ == "__main__":
    asyncio.run(register_and_start_consuming())
