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
    read_events = []
    async for ev in task.events():
        if "text" in ev:
            read_events.append(ev)
    assert len(read_events) == 3
    # the workflow produces events sequentially, so here we can assume events arrived in order
    for i, ev in enumerate(read_events):
        assert ev["text"] == f"message number {i+1}"
