import asyncio
from pathlib import Path

import pytest
from llama_index.core.workflow.context_serializers import JsonSerializer
from llama_index.core.workflow.events import HumanResponseEvent

from llama_deploy.types import EventDefinition, TaskDefinition


@pytest.mark.asyncio
async def test_hitl(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment_hitl.yml"
    with open(deployment_fp) as f:
        deployment = await client.apiserver.deployments.create(
            f, base_path=deployment_fp.parent
        )
        await asyncio.sleep(5)

    tasks = deployment.tasks
    task = await tasks.create(TaskDefinition(input="{}"))
    ev = HumanResponseEvent(response="42")
    r = await task.send_event(ev=ev, service_name="hitl_workflow")
    ev_def = EventDefinition.model_validate(r.model_dump())

    # wait for workflow to finish
    await asyncio.sleep(0.5)

    result = await task.results()

    assert ev_def.service_id == "hitl_workflow"
    assert ev_def.event_obj_str == JsonSerializer().serialize(ev)
    assert result.result == "42", "The human's response is not consistent."
