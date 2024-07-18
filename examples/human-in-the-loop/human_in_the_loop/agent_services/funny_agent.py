import asyncio
import uvicorn
from pathlib import Path

from llama_agents import AgentService, ServiceComponent
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.tools import FunctionTool, ToolMetadata
from llama_index.core.tools import QueryEngineTool
from llama_index.llms.openai import OpenAI
from llama_index.agent.openai import OpenAIAgent

from human_in_the_loop.utils import load_from_env


message_queue_host = load_from_env("RABBITMQ_HOST")
message_queue_port = load_from_env("RABBITMQ_NODE_PORT")
message_queue_username = load_from_env("RABBITMQ_DEFAULT_USER")
message_queue_password = load_from_env("RABBITMQ_DEFAULT_PASS")
control_plane_host = load_from_env("CONTROL_PLANE_HOST")
control_plane_port = load_from_env("CONTROL_PLANE_PORT")
funny_agent_host = load_from_env("FUNNY_AGENT_HOST")
funny_agent_port = load_from_env("FUNNY_AGENT_PORT")
localhost = load_from_env("LOCALHOST")


# create agent server
message_queue = RabbitMQMessageQueue(
    url=f"amqp://{message_queue_username}:{message_queue_password}@{message_queue_host}:{message_queue_port}/"
)


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


secret_fact_tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

# rag tool
data_path = Path(Path(__file__).parents[2].absolute(), "data").as_posix()
loader = SimpleDirectoryReader(input_dir=data_path)
documents = loader.load_data()
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine(llm=OpenAI(model="gpt-4o"))
query_engine_tool = QueryEngineTool(
    query_engine=query_engine,
    metadata=ToolMetadata(
        name="paul_graham_tool",
        description=("Provides information about Paul Graham and his written essays."),
    ),
)


agent = OpenAIAgent.from_tools(
    [secret_fact_tool, query_engine_tool],
    system_prompt="Knows about Paul Graham, the secret fact, and is able to tell a funny joke.",
    llm=OpenAI(model="gpt-4o"),
    verbose=True,
)
agent_server = AgentService(
    agent=agent,
    message_queue=message_queue,
    description="Useful for everything but math, and especially telling funny jokes and anything about Paul Graham.",
    service_name="funny_agent",
    host=funny_agent_host,
    port=int(funny_agent_port) if funny_agent_port else None,
)
agent_component = ServiceComponent.from_service_definition(agent_server)

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
