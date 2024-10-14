import asyncio
from pathlib import Path

import pytest

from llama_deploy.types import TaskDefinition


@pytest.mark.asyncio
async def test_stream(apiserver, client):
    here = Path(__file__).parent

    with open(here / "deployments" / "deployment_streaming.yml") as f:
        deployments = await client.apiserver.deployments()
        deployment = await deployments.create(f)
        await asyncio.sleep(5)

    tasks = await deployment.tasks()
    task = await tasks.create(TaskDefinition(input='{"a": "b"}'))
    async for ev in task.events():
        print(ev)
