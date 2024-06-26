from llama_agents import AgentService, SimpleMessageQueue

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.llms.openai import OpenAI


# create an agent
worker = FunctionCallingAgentWorker.from_tools([], llm=OpenAI())
agent = worker.as_agent()

# create agent server
message_queue = SimpleMessageQueue()
queue_client = message_queue.client

agent_server = AgentService(
    agent=agent,
    message_queue=queue_client,
    description="Useful for getting funny jokes.",
    service_name="funny_agent",
    host="127.0.0.1",
    port=8003,
)

app = agent_server._app
