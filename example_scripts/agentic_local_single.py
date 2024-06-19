from agentfile.launchers.local import LocalLauncher
from agentfile.services import AgentService
from agentfile.control_plane.fastapi import FastAPIControlPlane
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.orchestrators.agent import AgentOrchestrator

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

worker1 = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
worker2 = FunctionCallingAgentWorker.from_tools([], llm=OpenAI())
agent1 = worker1.as_agent()
agent2 = worker2.as_agent()

# create our multi-agent framework components
message_queue = SimpleMessageQueue()
control_plane = FastAPIControlPlane(
    message_queue=message_queue,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
)
agent_server_1 = AgentService(
    agent=agent1,
    message_queue=message_queue,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
)
agent_server_2 = AgentService(
    agent=agent2,
    message_queue=message_queue,
    description="Useful for getting random dumb facts.",
    service_name="dumb_fact_agent",
)

# launch it
launcher = LocalLauncher([agent_server_1, agent_server_2], control_plane, message_queue)
launcher.launch_single("What is the secret fact?")
