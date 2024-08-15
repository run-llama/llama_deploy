from llama_agents import (
    CallableMessageConsumer,
    ControlPlaneServer,
    HumanService,
    SimpleMessageQueue,
    SimpleOrchestrator,
    WorkflowService,
    ServerLauncher,
    QueueMessage,
)

from llama_index.core.workflow import Workflow, step, StartEvent, StopEvent
from llama_index.llms.openai import OpenAI


class JokeFlow(Workflow):
    @step()
    async def tell_joke(self, ev: StartEvent) -> StopEvent:
        topic = ev.get("topic")
        if not topic:
            raise ValueError("topic is required.")

        llm = OpenAI()
        response = llm.complete(f"Tell me a joke about {topic}")
        return StopEvent(result=str(response))


# create our multi-agent framework components
message_queue = SimpleMessageQueue(port=8001)

workflow_service = WorkflowService(
    JokeFlow(),
    message_queue.client,
    service_name="joke_flow",
    description="Service to tell jokes.",
    host="127.0.0.1",
    port=8002,
)
human_service = HumanService(
    message_queue=message_queue.client,
    description="Answers queries about math.",
    host="127.0.0.1",
    port=8004,
)


# additional human consumer
def handle_result(message: QueueMessage) -> None:
    print("Got result:", message.data)


human_consumer = CallableMessageConsumer(handler=handle_result, message_type="human")

simple_orchestrator = SimpleOrchestrator()

control_plane = ControlPlaneServer(
    message_queue,
    simple_orchestrator,
    port=8000,
)

# launch it
launcher = ServerLauncher(
    [workflow_service, human_service],
    control_plane,
    message_queue,
    additional_consumers=[human_consumer],
)

launcher.launch_servers()
