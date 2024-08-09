from llama_agents import (
    AgentService,
    ControlPlaneServer,
    PipelineOrchestrator,
    ServiceComponent,
    LocalLauncher,
)
from llama_agents.message_queues.aws_sqs import AWSMessageQueue
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from llama_index.core.query_pipeline import QueryPipeline, RouterComponent
from llama_index.core.selectors import PydanticSingleSelector
from llama_index.llms.openai import OpenAI


# Define a function that will be wrapped in a FunctionTool, to be used by our "secret fact" agent
def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


tool = FunctionTool.from_defaults(fn=get_the_secret_fact)

agent1 = ReActAgent.from_tools([tool], llm=OpenAI())
agent2 = ReActAgent.from_tools([], llm=OpenAI())

# Create our multi-agent framework components with SQS as the message queue
# Note that in this example, all messages will be processed in the order they are sent within their respective topics, ie. enforcing strict message ordering across different agents.
# You may want to use unique MessageGroupIds for different agents to allow for concurrency, if it fits your particular use case.
AWS_SNS_SQS_REGION = "us-east-1"

message_queue = AWSMessageQueue(region=AWS_SNS_SQS_REGION)

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
    description="Useful for getting random funny facts.",
    service_name="funny_fact_agent",
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
