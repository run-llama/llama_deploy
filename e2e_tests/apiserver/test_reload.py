import asyncio
from pathlib import Path

import pytest

from llama_deploy.types import TaskDefinition


@pytest.mark.asyncio
async def test_reload(apiserver, client):
    here = Path(__file__).parent
    with open(here / "deployments" / "deployment_reload1.yml") as f:
        deployment = await client.apiserver.deployments.create(f)
        await asyncio.sleep(3)

    tasks = deployment.tasks
    res = await tasks.run(TaskDefinition(input='{"data": "bar"}'))
    assert res == "I have received:bar"

    with open(here / "deployments" / "deployment_reload2.yml") as f:
        deployment = await client.apiserver.deployments.create(f, reload=True)
        await asyncio.sleep(3)

    tasks = deployment.tasks
    res = await tasks.run(TaskDefinition(input='{"data": "bar"}'))
    assert res == "Ho ricevuto:bar"
