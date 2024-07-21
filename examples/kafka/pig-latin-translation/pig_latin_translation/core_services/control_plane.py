import asyncio
import uvicorn

from llama_agents import ControlPlaneServer, PipelineOrchestrator, ServiceComponent
from llama_agents.message_queues.apache_kafka import KafkaMessageQueue
from llama_index.core.query_pipeline import QueryPipeline

from pig_latin_translation.utils import load_from_env
from pig_latin_translation.agent_services.remove_ay_agent import (
    agent_server as remove_ay_agent_server,
)
from pig_latin_translation.agent_services.correct_first_character_agent import (
    agent_server as correct_first_character_agent_server,
)

message_queue_host = load_from_env("KAFKA_HOST")
message_queue_port = load_from_env("KAFKA_PORT")
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")
localhost = load_from_env("LOCALHOST")


# setup message queue
message_queue = KafkaMessageQueue.from_url_params(
    host=message_queue_host,
    port=int(message_queue_port) if message_queue_port else None,
)

# setup control plane
remove_ay_agent_component = ServiceComponent.from_service_definition(
    remove_ay_agent_server
)
correct_first_character_agent_component = ServiceComponent.from_service_definition(
    correct_first_character_agent_server
)

pipeline = QueryPipeline(
    chain=[
        remove_ay_agent_component,
        correct_first_character_agent_component,
    ]
)

pipeline_orchestrator = PipelineOrchestrator(pipeline)

control_plane = ControlPlaneServer(
    message_queue=message_queue,
    orchestrator=pipeline_orchestrator,
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
        host=localhost,
        port=control_plane.port,
    )
    server = uvicorn.Server(cfg)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(launch())
