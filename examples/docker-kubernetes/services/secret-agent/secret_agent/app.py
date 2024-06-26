import nest_asyncio

from llama_agents import AgentService, SimpleMessageQueue

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI

nest_asyncio.apply()


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)
worker = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
agent = worker.as_agent()

# create agent server
message_queue = SimpleMessageQueue(host="0.0.0.0", port=8000)
queue_client = message_queue.client

agent_server = AgentService(
    agent=agent,
    message_queue=queue_client,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
    host="127.0.0.1",
    port=8001,
)

# registration
# tasks = [
#     agent_server.register_to_message_queue(),
#     agent_server.register_to_control_plane(control_plane_url="http://0.0.0.0:8001"),
# ]
# asyncio.run(asyncio.gather(*tasks))

app = agent_server._app
