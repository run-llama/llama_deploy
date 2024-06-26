import asyncio
from llama_agents import AgentOrchestrator, ControlPlaneServer, SimpleMessageQueue
from llama_index.llms.openai import OpenAI

# setup message queue
message_queue = SimpleMessageQueue(host="0.0.0.0", port=8000)
queue_client = message_queue.client

# setup control plane
control_plane = ControlPlaneServer(
    message_queue=queue_client,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
    host="0.0.0.0",
    port=8001,
)


app = control_plane.app


async def register() -> None:
    # register to message queue
    await queue_client.register_consumer(control_plane.as_consumer(remote=True))


if __name__ == "__main__":
    asyncio.run(register())
