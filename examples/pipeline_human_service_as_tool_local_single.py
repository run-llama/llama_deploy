from llama_agents import (
    AgentService,
    HumanService,
    ControlPlaneServer,
    SimpleMessageQueue,
    PipelineOrchestrator,
    ServiceComponent,
    LocalLauncher,
)
from llama_agents.tools import ServiceAsTool


from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.core.query_pipeline import QueryPipeline
from llama_index.llms.openai import OpenAI
from llama_index.agent.openai import OpenAIAgent


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

worker1 = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
# worker2 = FunctionCallingAgentWorker.from_tools([], llm=OpenAI())
agent1 = worker1.as_agent()

# create our multi-agent framework components
message_queue = SimpleMessageQueue()

human_service = HumanService(
    message_queue=message_queue,
    description="Answers queries about math.",
)

human_service_as_tool = ServiceAsTool.from_service_definition(
    message_queue=message_queue, service_definition=human_service.service_definition
)

agent = OpenAIAgent.from_tools(
    [human_service_as_tool],
    system_prompt="Perform the task, return the result as well as a funny joke.",
    llm=OpenAI(model="gpt-4o"),
)  # worker2.as_agent()
agent_server = AgentService(
    agent=agent,
    message_queue=message_queue,
    description="Useful for telling funny jokes.",
    service_name="funny_agent",
)

agent_component = ServiceComponent.from_service_definition(agent_server)

pipeline = QueryPipeline(chain=[agent_component])

pipeline_orchestrator = PipelineOrchestrator(pipeline)

control_plane = ControlPlaneServer(message_queue, pipeline_orchestrator)

# launch it
launcher = LocalLauncher([human_service, agent_server], control_plane, message_queue)
result = launcher.launch_single("What is 1+1+2+3+5+8?")

print(f"Result: {result}")
