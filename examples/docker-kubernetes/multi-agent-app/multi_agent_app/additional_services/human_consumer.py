import asyncio
from llama_agents import (
    SimpleMessageQueue,
)

from multi_agent_app.additional_services.task_result import TaskResultService
from multi_agent_app.utils import load_from_env

message_queue_host = load_from_env("MESSAGE_QUEUE_HOST")
message_queue_port = load_from_env("MESSAGE_QUEUE_PORT")
human_consumer_host = load_from_env("HUMAN_CONSUMER_HOST")
human_consumer_port = load_from_env("HUMAN_CONSUMER_PORT")

# create our multi-agent framework components
message_queue = SimpleMessageQueue(
    host=message_queue_host,
    port=int(message_queue_port) if message_queue_port else None,
)
queue_client = message_queue.client


human_consumer_server = TaskResultService(
    message_queue=queue_client,
    host=human_consumer_host,
    port=int(human_consumer_port) if human_consumer_port else None,
    name="human",
)

app = human_consumer_server._app


# register to message queue
async def register() -> None:
    await human_consumer_server.register_to_message_queue()


if __name__ == "__main__":
    asyncio.run(register())
