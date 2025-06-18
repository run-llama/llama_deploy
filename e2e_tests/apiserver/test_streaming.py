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

    task = await deployment.tasks.create(TaskDefinition(input='{"a": "b"}'))

    read_events = []
    async for ev in task.events():
        if ev and "text" in ev:
            read_events.append(ev)
    assert len(read_events) == 3
    # the workflow produces events sequentially, so here we can assume events arrived in order
    for i, ev in enumerate(read_events):
        assert ev["text"] == f"message number {i + 1}"
