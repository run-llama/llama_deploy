from llama_agents import (
    AgentService,
    HumanService,
    AgentOrchestrator,
    CallableMessageConsumer,
    ControlPlaneServer,
    ServerLauncher,
    QueueMessage,
)
from llama_agents.message_queues.rabbitmq import RabbitMQMessageQueue
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
message_queue = RabbitMQMessageQueue()
queue_client = message_queue.client


control_plane = ControlPlaneServer(
    message_queue=queue_client,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
)
agent_server_1 = AgentService(
    agent=agent1,
    message_queue=queue_client,
    description="Useful for getting the secret fact.",
    service_name="secret_fact_agent",
    host="127.0.0.1",
    port=8002,
)
agent_server_2 = AgentService(
    agent=agent2,
    message_queue=queue_client,
    description="Useful for getting random dumb facts.",
    service_name="dumb_fact_agent",
    host="127.0.0.1",
    port=8003,
)
human_service = HumanService(
    message_queue=queue_client,
    description="Answers queries about math.",
    host="127.0.0.1",
    port=8004,
)


# additional human consumer
def handle_result(message: QueueMessage) -> None:
    print("Got result:", message.data)


human_consumer = CallableMessageConsumer(handler=handle_result, message_type="human")

# launch it
launcher = ServerLauncher(
    [agent_server_1, agent_server_2, human_service],
    control_plane,
    message_queue,
    additional_consumers=[human_consumer],
)

launcher.launch_servers()
