from llama_agents import AgentOrchestrator, ControlPlaneServer, SimpleMessageQueue
from llama_index.llms.openai import OpenAI

# setup message queue
message_queue = SimpleMessageQueue()
queue_client = message_queue.client

# setup control plane
control_plane = ControlPlaneServer(
    message_queue=queue_client,
    orchestrator=AgentOrchestrator(llm=OpenAI()),
)
app = control_plane.app
