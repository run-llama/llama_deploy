import asyncio
import uvicorn
from human_in_the_loop.apps.gradio_app import updated_human_service as human_service
from human_in_the_loop.utils import load_from_env

message_queue_host = load_from_env("RABBITMQ_HOST")
message_queue_port = load_from_env("RABBITMQ_NODE_PORT")
message_queue_username = load_from_env("RABBITMQ_DEFAULT_USER")
message_queue_password = load_from_env("RABBITMQ_DEFAULT_PASS")
human_in_the_loop_host = load_from_env("HUMAN_IN_THE_LOOP_HOST")
human_in_the_loop_port = load_from_env("HUMAN_IN_THE_LOOP_PORT")
localhost = load_from_env("LOCALHOST")


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
