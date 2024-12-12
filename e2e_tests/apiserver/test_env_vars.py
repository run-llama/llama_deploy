import asyncio
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_read_env_vars(apiserver, client):
    here = Path(__file__).parent

    with open(here / "deployments" / "deployment_env.yml") as f:
        await client.apiserver.deployments.create(f)
        await asyncio.sleep(5)

    session = await client.core.sessions.create()

    # run workflow
    result_1 = await session.run("test_env_workflow")
    result_2 = await session.run("another_workflow")

    assert result_1 == "var_1: z, var_2: y, api_key: 123"
    assert result_2 == "var_1: w, var_2: z, api_key: 456"
