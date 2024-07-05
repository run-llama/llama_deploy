import asyncio
import uvicorn
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue
from multi_agent_app_rabbitmq.additional_services.task_result import TaskResultService
from multi_agent_app_rabbitmq.utils import load_from_env

message_queue_host = load_from_env("RABBITMQ_HOST")
message_queue_port = load_from_env("RABBITMQ_NODE_PORT")
message_queue_username = load_from_env("RABBITMQ_DEFAULT_USER")
message_queue_password = load_from_env("RABBITMQ_DEFAULT_PASS")
human_consumer_host = load_from_env("HUMAN_CONSUMER_HOST")
human_consumer_port = load_from_env("HUMAN_CONSUMER_PORT")
localhost = load_from_env("LOCALHOST")


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


# launch
async def launch() -> None:
    # register to message queue and start consuming
    start_consuming_callable = await human_consumer_server.register_to_message_queue()
    _ = asyncio.create_task(start_consuming_callable())

    cfg = uvicorn.Config(
        human_consumer_server._app,
        host=localhost,
        port=human_consumer_server.port,
    )
    server = uvicorn.Server(cfg)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(launch())
