from llama_agents import (
    AgentService,
    ControlPlaneServer,
    PipelineOrchestrator,
    ServiceComponent,
)
from llama_agents.tools import AgentServiceTool
from llama_agents.message_queues.async_rabbitmq import AsyncRabbitMQMessageQueue
from llama_agents.launchers.local_asyncrabbitmq import LocalAsyncRabbitMQLauncher


from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.core.query_pipeline import QueryPipeline
from llama_index.llms.openai import OpenAI
from llama_index.agent.openai import OpenAIAgent


# logging.basicConfig(stream=sys.stdout, level=logging.INFO)
# logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

worker1 = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
# worker2 = FunctionCallingAgentWorker.from_tools([], llm=OpenAI())
agent1 = worker1.as_agent()

# create our multi-agent framework components
message_queue = AsyncRabbitMQMessageQueue()

agent1_server = AgentService(
    agent=agent1,
    message_queue=message_queue,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
)

agent1_server_tool = AgentServiceTool.from_service_definition(
    message_queue=message_queue, service_definition=agent1_server.service_definition
)

agent2 = OpenAIAgent.from_tools(
    [agent1_server_tool],
    system_prompt="Perform the task, return the result as well as a funny joke.",
)  # worker2.as_agent()
agent2_server = AgentService(
    agent=agent2,
    message_queue=message_queue,
    description="Useful for telling funny jokes.",
    service_name="dumb_fact_agent",
)

agent2_component = ServiceComponent.from_service_definition(agent2_server)

pipeline = QueryPipeline(chain=[agent2_component])

pipeline_orchestrator = PipelineOrchestrator(pipeline)

control_plane = ControlPlaneServer(message_queue, pipeline_orchestrator)

# launch it
launcher = LocalAsyncRabbitMQLauncher(
    [agent1_server, agent2_server], control_plane, message_queue
)
result = launcher.launch_single("What is the secret fact?")

print(f"Result: {result}")
