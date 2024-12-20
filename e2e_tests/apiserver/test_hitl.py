import asyncio
from pathlib import Path

import pytest

from llama_deploy.types import TaskDefinition, EventDefinition

from llama_index.core.workflow.events import HumanResponseEvent
from llama_index.core.workflow.context_serializers import JsonSerializer


@pytest.mark.asyncio
async def test_hitl(apiserver, client):
    here = Path(__file__).parent

    with open(here / "deployments" / "deployment_hitl.yml") as f:
        deployment = await client.apiserver.deployments.create(f)
        await asyncio.sleep(5)

    tasks = deployment.tasks
    task = await tasks.create(TaskDefinition(input="{}"))
    ev = HumanResponseEvent(response="42")
    r = await task.send_event(ev=ev, service_name="hitl_workflow")
    ev_def = EventDefinition.model_validate(r.model_dump())

    # wait for workflow to finish
    await asyncio.sleep(0.5)

    result = await task.results()

    assert ev_def.agent_id == "hitl_workflow"
    assert ev_def.event_obj_str == JsonSerializer().serialize(ev)
    assert result.result == "42", "The human's response is not consistent."
