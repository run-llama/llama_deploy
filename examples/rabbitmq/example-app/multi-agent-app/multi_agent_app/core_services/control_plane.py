import asyncio
import uvicorn

from llama_agents import AgentOrchestrator, ControlPlaneServer
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue
from llama_index.llms.openai import OpenAI

from multi_agent_app.utils import load_from_env


message_queue_host = load_from_env("RABBITMQ_HOST")
message_queue_port = load_from_env("RABBITMQ_NODE_PORT")
message_queue_username = load_from_env("RABBITMQ_DEFAULT_USER")
message_queue_password = load_from_env("RABBITMQ_DEFAULT_PASS")
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")
external_host = load_from_env("EXTERNAL_HOST")


# setup message queue
message_queue = RabbitMQMessageQueue(
    url=f"amqp://{message_queue_username}:{message_queue_password}@{message_queue_host}:{message_queue_port}/"
)

# setup control plane
control_plane = ControlPlaneServer(
    message_queue=message_queue,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
    host=control_plane_host,
    port=int(control_plane_port) if control_plane_port else None,
)


app = control_plane.app


# launch
async def launch() -> None:
    # register to message queue and start consuming
    start_consuming_callable = await control_plane.register_to_message_queue()
    _ = asyncio.create_task(start_consuming_callable())

    cfg = uvicorn.Config(
        control_plane.app,
        host=external_host,
        port=control_plane.port,
    )
    server = uvicorn.Server(cfg)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(launch())
