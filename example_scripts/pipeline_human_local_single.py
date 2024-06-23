from llama_agents import (
    AgentService,
    HumanService,
    ControlPlaneServer,
    SimpleMessageQueue,
    PipelineOrchestrator,
    ServiceComponent,
    LocalLauncher,
)

from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.core.query_pipeline import RouterComponent, QueryPipeline
from llama_index.llms.openai import OpenAI
from llama_index.core.selectors import PydanticSingleSelector


# create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

# create our multi-agent framework components
message_queue = SimpleMessageQueue()

worker = FunctionCallingAgentWorker.from_tools([tool], llm=OpenAI())
agent = worker.as_agent()
agent_service = AgentService(
    agent=agent,
    message_queue=message_queue,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
)
agent_component = ServiceComponent.from_service_definition(agent_service)

human_service = HumanService(
    message_queue=message_queue, description="Answers queries about math."
)
human_component = ServiceComponent.from_service_definition(human_service)

pipeline = QueryPipeline(
    chain=[
        RouterComponent(
            selector=PydanticSingleSelector.from_defaults(llm=OpenAI()),
            choices=[agent_service.description, human_service.description],
            components=[agent_component, human_component],
        )
    ]
)

pipeline_orchestrator = PipelineOrchestrator(pipeline)

control_plane = ControlPlaneServer(message_queue, pipeline_orchestrator)

# launch it
launcher = LocalLauncher([agent_service, human_service], control_plane, message_queue)
result = launcher.launch_single("What is 1 + 2 + 3 + 4 + 5?")

print(f"Result: {result}")
