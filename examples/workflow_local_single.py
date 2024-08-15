from llama_agents import (
    ControlPlaneServer,
    SimpleMessageQueue,
    SimpleOrchestrator,
    WorkflowService,
    LocalLauncher,
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
message_queue = SimpleMessageQueue()

workflow_service = WorkflowService(
    JokeFlow(),
    message_queue,
    service_name="joke_flow",
    description="Service to tell jokes.",
)

simple_orchestrator = SimpleOrchestrator()

control_plane = ControlPlaneServer(message_queue, simple_orchestrator)

# launch it
launcher = LocalLauncher([workflow_service], control_plane, message_queue)
result = launcher.launch_single("""{"topic": "llamas"}""", service_id="joke_flow")

print(f"Result: {result}")
