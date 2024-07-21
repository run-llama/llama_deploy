import asyncio
import uvicorn

from llama_agents import AgentService
from llama_agents.message_queues.apache_kafka import KafkaMessageQueue

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

from pig_latin_translation.utils import load_from_env
from pig_latin_translation.agent_services.decorators import exponential_delay

from logging import getLogger

logger = getLogger(__name__)

message_queue_host = load_from_env("KAFKA_HOST")
message_queue_port = load_from_env("KAFKA_PORT")
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")
remove_ay_agent_host = load_from_env("AY_AGENT_HOST")
remove_ay_agent_port = load_from_env("AY_AGENT_PORT")
localhost = load_from_env("LOCALHOST")


STARTUP_RATE = 3
SYSTEM_PROMPT = """Pass the entire sentence to the remove 'ay' suffix tool.
The tool will remove 'ay' from every word in the sentence.
Do not send tokens one at a time to the tool!
Do not call the tool more than once!
"""


# create an agent
@exponential_delay(STARTUP_RATE)
def sync_remove_ay_suffix(input_sentence: str) -> str:
    """Removes 'ay' suffix from each token in the input_sentence.

    Params:
        input_sentence (str): The input sentence i.e., sequence of words
    """
    logger.info(f"received task input: {input_sentence}")
    tokens = input_sentence.split()
    res = " ".join([t[:-2] for t in tokens])
    logger.info(f"Removed 'ay' suffix: {res}")
    return res


@exponential_delay(STARTUP_RATE)
async def async_remove_ay_suffix(input_sentence: str) -> str:
    """Removes 'ay' suffix from each token in the input_sentence.

    Params:
        input_sentence (str): The input sentence i.e., sequence of words
    """
    logger.info(f"received task input: {input_sentence}")
    tokens = input_sentence.split()
    res = " ".join([t[:-2] for t in tokens])
    logger.info(f"Removed 'ay' suffix: {res}")
    return res


tool = FunctionTool.from_defaults(
    fn=sync_remove_ay_suffix, async_fn=async_remove_ay_suffix
)
worker = FunctionCallingAgentWorker.from_tools(
    [tool], llm=OpenAI(), system_prompt=SYSTEM_PROMPT, max_function_calls=1
)
agent = worker.as_agent()

# create agent server
message_queue = KafkaMessageQueue.from_url_params(
    host=message_queue_host,
    port=int(message_queue_port) if message_queue_port else None,
)

agent_server = AgentService(
    agent=agent,
    message_queue=message_queue,
    description="Removes the 'ay' suffix from each token from a provided input_sentence.",
    service_name="remove_ay_agent",
    host=remove_ay_agent_host,
    port=int(remove_ay_agent_port) if remove_ay_agent_port else None,
)

app = agent_server._app


# launch
async def launch() -> None:
    # register to message queue
    start_consuming_callable = await agent_server.register_to_message_queue()
    _ = asyncio.create_task(start_consuming_callable())

    # register to control plane
    await agent_server.register_to_control_plane(
        control_plane_url=(
            f"http://{control_plane_host}:{control_plane_port}"
            if control_plane_port
            else f"http://{control_plane_host}"
        )
    )

    cfg = uvicorn.Config(
        agent_server._app,
        host=localhost,
        port=agent_server.port,
    )
    server = uvicorn.Server(cfg)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(launch())
