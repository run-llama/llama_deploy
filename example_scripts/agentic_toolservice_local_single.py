from agentfile.launchers.local import LocalLauncher
from agentfile.services import AgentService, ToolService
from agentfile.tools import MetaServiceTool
from agentfile.control_plane.fastapi import ControlPlaneServer
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


# create our multi-agent framework components
message_queue = SimpleMessageQueue()
tool_service = ToolService(
    message_queue=message_queue,
    tools=[tool],
    running=True,
    step_interval=0.5,
)

control_plane = ControlPlaneServer(
    message_queue=message_queue,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
)

meta_tool = MetaServiceTool(
    tool_metadata=tool.metadata,
    message_queue=message_queue,
    tool_service_name=tool_service.service_name,
)
worker1 = FunctionCallingAgentWorker.from_tools(
    [meta_tool],
    llm=OpenAI(),
)
agent1 = worker1.as_agent()
agent_server_1 = AgentService(
    agent=agent1,
    message_queue=message_queue,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
)

# launch it
launcher = LocalLauncher(
    [agent_server_1, tool_service],
    control_plane,
    message_queue,
)
result = launcher.launch_single("What is the secret fact?")

print(f"Result: {result}")
