import asyncio
from llama_agents import (
    AgentService,
    ControlPlaneServer,
    PipelineOrchestrator,
    ServiceComponent,
    LocalLauncher
)
from llama_agents.message_queues.aws_sqs import SQSMessageQueue
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.core.query_pipeline import QueryPipeline, RouterComponent
from llama_index.core.selectors import PydanticSingleSelector
from llama_index.llms.openai import OpenAI

# Create an agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."

tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

agent1 = ReActAgent.from_tools([tool], llm=OpenAI())
agent2 = ReActAgent.from_tools([], llm=OpenAI())

# Create our multi-agent framework components with SQS as the message queue
message_queue = SQSMessageQueue(region="us-west-2", queue_name="llama-agents")

agent_server_1 = AgentService(
    agent=agent1,
    message_queue=message_queue,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
    port=8002,
)

agent_server_2 = AgentService(
    agent=agent2,
    message_queue=message_queue,
    description="Useful for getting random dumb facts.",
    service_name="dumb_fact_agent",
    port=8003,
)

agent_component_1 = ServiceComponent.from_service_definition(agent_server_1)
agent_component_2 = ServiceComponent.from_service_definition(agent_server_2)

pipeline = QueryPipeline(
    chain=[
        RouterComponent(
            selector=PydanticSingleSelector.from_defaults(llm=OpenAI()),
            choices=[agent_server_1.description, agent_server_2.description],
            components=[agent_component_1, agent_component_2],
        )
    ]
)

pipeline_orchestrator = PipelineOrchestrator(pipeline)

control_plane = ControlPlaneServer(message_queue, pipeline_orchestrator, port=8001)

# Launch it
launcher = LocalLauncher([agent_server_1, agent_server_2], control_plane, message_queue)
result = launcher.launch_single("What is the secret fact?")

print(f"Result: {result}")
