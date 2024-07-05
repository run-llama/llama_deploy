import asyncio
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue
from multi_agent_app.additional_services.task_result import TaskResultService
from multi_agent_app.utils import load_from_env

message_queue_host = load_from_env("RABBITMQ_HOST")
message_queue_port = load_from_env("RABBITMQ_NODE_PORT")
message_queue_username = load_from_env("RABBITMQ_DEFAULT_USER")
message_queue_password = load_from_env("RABBITMQ_DEFAULT_PASS")
human_consumer_host = load_from_env("HUMAN_CONSUMER_HOST")
human_consumer_port = load_from_env("HUMAN_CONSUMER_PORT")

# create our multi-agent framework components
message_queue = RabbitMQMessageQueue(
    url=f"amqp://{message_queue_username}:{message_queue_password}@{message_queue_host}:{message_queue_port}/"
)

human_consumer_server = TaskResultService(
    message_queue=message_queue,
    host=human_consumer_host,
    port=int(human_consumer_port) if human_consumer_port else None,
    name="human",
)

app = human_consumer_server._app


# register to message queue
async def register_and_start_consuming() -> None:
    start_consuming_callable = await human_consumer_server.register_to_message_queue()
    await start_consuming_callable()


if __name__ == "__main__":
    asyncio.run(register_and_start_consuming())
