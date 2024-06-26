import asyncio
import os
from llama_agents import (
    SimpleMessageQueue,
)

from human_consumer.task_result_service import TaskResultService


try:
    message_queue_host = os.environ["MESSAGE_QUEUE_HOST"]
except KeyError:
    raise ValueError("Missing env var `MESSAGE_QUEUE_HOST`.")

try:
    human_consumer_host = os.environ["HUMAN_CONSUMER_HOST"]
except KeyError:
    raise ValueError("Missing env var `HUMAN_CONSUMER_HOST`.")

# create our multi-agent framework components
message_queue = SimpleMessageQueue(host=message_queue_host, port=8000)
queue_client = message_queue.client


human_consumer = TaskResultService(
    message_queue=queue_client, host=human_consumer_host, port=8004, name="human"
)

app = human_consumer._app


# register to message queue
async def register() -> None:
    await human_consumer.register_to_message_queue()


if __name__ == "__main__":
    asyncio.run(register())
