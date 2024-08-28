import asyncio
import pytest
from llama_agents import (
    deploy_core,
    deploy_workflow,
    ControlPlaneConfig,
    SimpleMessageQueueConfig,
    WorkflowServiceConfig,
    AsyncLlamaAgentsClient,
)
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, step


class MyWorkflow(Workflow):
    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        arg1 = ev.get("arg1")
        if not arg1:
            raise ValueError("arg1 is required.")

        return StopEvent(result=str(arg1) + "_result")


def deploy_dummy_core() -> asyncio.Task:
    return asyncio.create_task(
        deploy_core(
            ControlPlaneConfig(),
            SimpleMessageQueueConfig(),
        )
    )


def deploy_dummy_workflow() -> asyncio.Task:
    return asyncio.create_task(
        deploy_workflow(
            MyWorkflow(),
            WorkflowServiceConfig(
                host="127.0.0.1", port=8002, service_name="my_workflow"
            ),
            ControlPlaneConfig(),
            SimpleMessageQueueConfig(),
        )
    )


@pytest.mark.asyncio()
async def test_async_client() -> None:
    core_task = deploy_dummy_core()

    await asyncio.sleep(1)

    workflow_task = deploy_dummy_workflow()

    await asyncio.sleep(1)

    client = AsyncLlamaAgentsClient(ControlPlaneConfig())

    sessions = await client.list_sessions()
    assert len(sessions) == 0

    services = await client.list_services()
    assert services[0].service_name == "my_workflow"

    session = await client.get_or_create_session("my_session")
    sessions = await client.list_sessions()
    assert len(sessions) == 1
    assert sessions[0].session_id == "my_session"

    result = session.run("my_workflow", arg1="hello_world")
    assert result == "hello_world_result"

    core_task.cancel()
    workflow_task.cancel()
