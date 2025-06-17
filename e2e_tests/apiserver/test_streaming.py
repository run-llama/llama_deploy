from pathlib import Path

import pytest

from llama_deploy.types import TaskDefinition


@pytest.mark.asyncio
async def test_stream(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment_streaming.yml"
    with open(deployment_fp) as f:
        deployment = await client.apiserver.deployments.create(
            f, base_path=deployment_fp.parent
        )

    tasks = deployment.tasks
    task = await tasks.create(TaskDefinition(input='{"a": "b"}'))

    read_events = []
    async for ev in task.events():
        if ev:
            read_events.append(ev)
    assert len(read_events) == 3
    # the workflow produces events sequentially, so here we can assume events arrived in order
    for i, ev in enumerate(read_events):
        assert ev == f"message number {i + 1}"
