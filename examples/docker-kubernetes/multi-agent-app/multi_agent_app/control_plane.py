import asyncio
import os

from llama_agents import AgentOrchestrator, ControlPlaneServer, SimpleMessageQueue
from llama_index.llms.openai import OpenAI


try:
    message_queue_host = os.environ["MESSAGE_QUEUE_HOST"]
except KeyError:
    raise ValueError("Missing env var `MESSAGE_QUEUE_HOST`.")

try:
    control_plane_host = os.environ["CONTROL_PLANE_HOST"]
except KeyError:
    raise ValueError("Missing env var `CONTROL_PLANE_HOST`.")


# setup message queue
message_queue = SimpleMessageQueue(host=message_queue_host, port=8000)
queue_client = message_queue.client

# setup control plane
control_plane = ControlPlaneServer(
    message_queue=queue_client,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
    host=control_plane_host,
    port=8001,
)


app = control_plane.app


async def register() -> None:
    # register to message queue
    await queue_client.register_consumer(control_plane.as_consumer(remote=True))


if __name__ == "__main__":
    asyncio.run(register())
