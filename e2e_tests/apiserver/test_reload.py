import asyncio
from pathlib import Path

import pytest

from llama_deploy.types import TaskDefinition


@pytest.mark.asyncio
async def test_reload(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment_reload1.yml"
    with open(deployment_fp) as f:
        deployment = await client.apiserver.deployments.create(
            f, base_path=deployment_fp.parent
        )
        await asyncio.sleep(3)

    tasks = deployment.tasks
    res = await tasks.run(TaskDefinition(input='{"data": "bar"}'))
    assert res == "I have received:bar"

    deployment_fp = here / "deployments" / "deployment_reload2.yml"
    with open(deployment_fp) as f:
        deployment = await client.apiserver.deployments.create(
            f, base_path=deployment_fp.parent, reload=True
        )
        await asyncio.sleep(3)

    tasks = deployment.tasks
    res = await tasks.run(TaskDefinition(input='{"data": "bar"}'))
    assert res == "Ho ricevuto:bar"
