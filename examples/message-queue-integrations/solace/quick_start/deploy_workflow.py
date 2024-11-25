import asyncio
from dotenv import load_dotenv, find_dotenv
from datetime import datetime
from llama_deploy import (
    deploy_workflow,
    WorkflowServiceConfig,
    ControlPlaneConfig,
)
from llama_index.core.workflow import (
    Context,
    Event,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)


class ProgressEvent(Event):
    progress: str


# create a dummy workflow
class PingWorkflow(Workflow):
    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        # Your workflow logic here
        arg1 = str(ev.get("arg1", ""))
        result = arg1 + "_result"

        # stream events as steps run
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ctx.write_event_to_stream(ProgressEvent(progress=f"{current_time}: Ping Ping!"))

        return StopEvent(result=result)


# create a dummy workflow
class HelloWorkflow(Workflow):
    @step()
    async def run_step(self, ctx: Context, ev: StartEvent) -> StopEvent:
        # Your workflow logic here
        arg1 = str(ev.get("arg1", ""))
        result = arg1 + "_result"

        # stream events as steps run
        ctx.write_event_to_stream(ProgressEvent(progress="Hello!"))

        return StopEvent(result=result)


def load_env():
    # Load environment variables from .env.solace file
    dotenv_path = find_dotenv(".env.solace")
    if not dotenv_path:
        raise FileNotFoundError(".env.solace file not found")

    load_dotenv(dotenv_path)


async def main():
    flow1 = deploy_workflow(
        workflow=PingWorkflow(),
        workflow_config=WorkflowServiceConfig(
            host="127.0.0.1", port=8002, service_name="ping_workflow"
        ),
        control_plane_config=ControlPlaneConfig(),
    )

    flow2 = deploy_workflow(
        workflow=HelloWorkflow(),
        workflow_config=WorkflowServiceConfig(
            host="127.0.0.1", port=8003, service_name="hello_workflow"
        ),
        control_plane_config=ControlPlaneConfig(),
    )

    # Run both tasks concurrently
    await asyncio.gather(flow1, flow2)


if __name__ == "__main__":
    load_env()
    asyncio.run(main())
