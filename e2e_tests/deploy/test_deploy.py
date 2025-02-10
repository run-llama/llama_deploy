import asyncio
import logging

import pytest
from llama_index.core.workflow import StartEvent, StopEvent, Workflow, step

from llama_deploy import Client, ControlPlaneConfig, SimpleMessageQueueConfig
from llama_deploy.deploy import deploy_core, deploy_workflow
from llama_deploy.services import WorkflowServiceConfig


class BasicWorkflow(Workflow):
    @step()
    async def run_step(self, ev: StartEvent) -> StopEvent:
        return StopEvent(result="done")


@pytest.mark.asyncio
async def test_deploy_core(caplog):
    caplog.set_level(logging.INFO)
    t = asyncio.create_task(
        deploy_core(
            control_plane_config=ControlPlaneConfig(),
            message_queue_config=SimpleMessageQueueConfig(),
        )
    )

    await asyncio.sleep(5)
    assert "Launching message queue server at" in caplog.text
    assert "Launching control plane server at" in caplog.text

    t.cancel()
    try:
        await asyncio.wait_for(t, timeout=5)
    except asyncio.TimeoutError:
        pass


@pytest.mark.asyncio
async def test_deploy_core_disable_control_plane(caplog):
    caplog.set_level(logging.INFO)
    t = asyncio.create_task(
        deploy_core(
            control_plane_config=ControlPlaneConfig(),
            message_queue_config=SimpleMessageQueueConfig(),
            disable_control_plane=True,
        )
    )

    await asyncio.sleep(5)
    assert "Launching message queue server at" in caplog.text
    assert "Launching control plane server at" not in caplog.text

    t.cancel()
    try:
        await asyncio.wait_for(t, timeout=5)
    except asyncio.TimeoutError:
        pass


@pytest.mark.asyncio
async def test_deploy_workflow():
    core_task = asyncio.create_task(deploy_core())
    await asyncio.sleep(3)

    service_task = asyncio.create_task(
        deploy_workflow(
            BasicWorkflow(),
            WorkflowServiceConfig(
                host="127.0.0.1", port=8002, service_name="my_workflow"
            ),
        )
    )
    await asyncio.sleep(3)

    client = Client()
    session = await client.core.sessions.get_or_create("fake_session_id")
    result = await session.run("my_workflow", arg1="")
    assert result == "done"

    core_task.cancel()
    service_task.cancel()
    await asyncio.gather(core_task, service_task, return_exceptions=True)


@pytest.mark.asyncio
async def test_deploy_workflow_reload():
    client = Client()
    core_task = asyncio.create_task(deploy_core())
    await asyncio.sleep(5)

    # Deploy the workflow a first time
    service_task = asyncio.create_task(
        deploy_workflow(
            BasicWorkflow(),
            WorkflowServiceConfig(
                host="127.0.0.1", port=8002, service_name="my_workflow"
            ),
        )
    )
    await asyncio.sleep(3)

    # Cancel the workflow service
    service_task.cancel()
    await service_task

    # Deploy the same workflow a second time
    service_task = asyncio.create_task(
        deploy_workflow(
            BasicWorkflow(),
            WorkflowServiceConfig(
                host="127.0.0.1", port=8002, service_name="my_workflow"
            ),
        )
    )
    await asyncio.sleep(3)

    session = await client.core.sessions.get_or_create("fake_session_id")
    result = await session.run("my_workflow", arg1="")
    assert result == "done"

    # Tear down
    service_task.cancel()
    await service_task
    core_task.cancel()
    await core_task
