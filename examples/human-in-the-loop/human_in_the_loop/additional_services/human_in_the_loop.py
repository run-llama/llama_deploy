import asyncio
import uvicorn
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue
from llama_agents.services.human import HumanService
from llama_agents.tools.service_as_tool import ServiceAsTool
from human_in_the_loop.utils import load_from_env

message_queue_host = load_from_env("RABBITMQ_HOST")
message_queue_port = load_from_env("RABBITMQ_NODE_PORT")
message_queue_username = load_from_env("RABBITMQ_DEFAULT_USER")
message_queue_password = load_from_env("RABBITMQ_DEFAULT_PASS")
human_in_the_loop_host = load_from_env("HUMAN_IN_THE_LOOP_HOST")
human_in_the_loop_port = load_from_env("HUMAN_IN_THE_LOOP_PORT")
localhost = load_from_env("LOCALHOST")


# create our multi-agent framework components
message_queue = RabbitMQMessageQueue(
    url=f"amqp://{message_queue_username}:{message_queue_password}@{message_queue_host}:{message_queue_port}/"
)


human_service = HumanService(
    message_queue=message_queue,
    description="Answers queries about math.",
    host=human_in_the_loop_host,
    port=int(human_in_the_loop_port) if human_in_the_loop_port else None,
)

human_service_as_tool = ServiceAsTool.from_service_definition(
    message_queue=message_queue, service_definition=human_service.service_definition
)


# launch
async def launch() -> None:
    # register to message queue
    start_consuming_callable = await human_service.register_to_message_queue()
    _ = asyncio.create_task(start_consuming_callable())

    cfg = uvicorn.Config(
        human_service._app,
        host=localhost,
        port=human_service.port,
    )
    server = uvicorn.Server(cfg)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(launch())
