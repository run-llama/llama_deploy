import asyncio
from pathlib import Path

import pytest

from llama_deploy.types import TaskDefinition

from llama_index.core.workflow.events import HumanResponseEvent


@pytest.mark.asyncio
async def test_hitl(apiserver, client):
    here = Path(__file__).parent

    with open(here / "deployments" / "deployment_hitl.yml") as f:
        deployment = await client.apiserver.deployments.create(f)
        await asyncio.sleep(5)

    tasks = deployment.tasks
    task = await tasks.create(TaskDefinition(input="{}"))
    r = await task.send_human_response(response="42", service_name="hitl_workflow")
    ev = HumanResponseEvent.model_validate(r.model_dump())

    # wait for workflow to finish
    await asyncio.sleep(0.5)

    result = await task.results()

    assert ev.response == "42"
    assert result.result == "42", "The human's response is not consistent."
