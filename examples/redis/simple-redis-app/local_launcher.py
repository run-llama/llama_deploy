from llama_agents import (
    AgentService,
    ControlPlaneServer,
    PipelineOrchestrator,
    ServiceComponent,
)
from llama_agents.tools import AgentServiceTool
from llama_agents.message_queues.redis import RedisMessageQueue
from llama_agents.launchers.local import LocalLauncher


from llama_index.core.agent import FunctionCallingAgentWorker
from llama_index.core.tools import FunctionTool
from llama_index.core.query_pipeline import QueryPipeline
from llama_index.llms.openai import OpenAI
from llama_index.agent.openai import OpenAIAgent


def get_the_secret_fact() -> str:
    """Returns the secret fact."""
    return "The secret fact is: A baby llama is called a 'Cria'."


message_queue = RedisMessageQueue()

secret_fact_tool = FunctionTool.from_defaults(fn=get_the_secret_fact)
secret_fact_worker = FunctionCallingAgentWorker.from_tools(
    [secret_fact_tool], llm=OpenAI()
)
secret_fact_agent = secret_fact_worker.as_agent()
secret_fact_agent_service = AgentService(
    agent=secret_fact_agent,
    message_queue=message_queue,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent_service",
)
secret_fact_agent_tool = AgentServiceTool.from_service_definition(
    message_queue=message_queue,
    service_definition=secret_fact_agent_service.service_definition,
)

funny_fact_agent = OpenAIAgent.from_tools(
    [secret_fact_agent_tool],
    system_prompt="Perform the task, return the result as well as a funny joke.",
)
funny_fact_agent_service = AgentService(
    agent=funny_fact_agent,
    message_queue=message_queue,
    description="Useful for telling funny jokes.",
    service_name="dumb_fact_agent",
)
funny_fact_agent_component = ServiceComponent.from_service_definition(
    funny_fact_agent_service
)

pipeline = QueryPipeline(chain=[funny_fact_agent_component])
pipeline_orchestrator = PipelineOrchestrator(pipeline)
control_plane = ControlPlaneServer(
    message_queue=message_queue, orchestrator=pipeline_orchestrator
)

# launch it
launcher = LocalLauncher(
    services=[secret_fact_agent_service, funny_fact_agent_service],
    control_plane=control_plane,
    message_queue=message_queue,
)
result = launcher.launch_single("What is the secret fact?")

print(f"Result: {result}")
