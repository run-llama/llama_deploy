from agentfile.launchers.local import LocalLauncher
from agentfile.services import HumanService
from agentfile.control_plane.fastapi import FastAPIControlPlane
from agentfile.message_queues.simple import SimpleMessageQueue
from agentfile.orchestrators.agent import AgentOrchestrator

from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)


# create our multi-agent framework components
message_queue = SimpleMessageQueue()

human_service = HumanService(
    message_queue=message_queue,
)

control_plane = FastAPIControlPlane(
    message_queue=message_queue,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
)


# launch it
launcher = LocalLauncher(
    [human_service],
    control_plane,
    message_queue,
)
launcher.launch_single("What is the secret fact?")
