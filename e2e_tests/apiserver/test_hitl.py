import asyncio
from pathlib import Path

import pytest
from workflows.events import HumanResponseEvent

from llama_deploy.types import TaskDefinition


@pytest.mark.asyncio
async def test_hitl(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment_hitl.yml"
    with open(deployment_fp) as f:
        deployment = await client.apiserver.deployments.create(
            f, base_path=deployment_fp.parent
        )

    task_handler = await deployment.tasks.create(TaskDefinition(input="{}"))
    ev_def = await task_handler.send_event(
        ev=HumanResponseEvent(response="42"), service_name="hitl_workflow"
    )

    # wait for workflow to finish
    await asyncio.sleep(0.1)

    result = await task_handler.results()
    assert ev_def.service_id == "hitl_workflow"
    assert result.result == "42", "The human's response is not consistent."
