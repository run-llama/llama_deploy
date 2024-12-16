import asyncio
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_read_env_vars_local(apiserver, client):
    here = Path(__file__).parent

    with open(here / "deployments" / "deployment_env_local.yml") as f:
        await client.apiserver.deployments.create(f)
        await asyncio.sleep(5)

    session = await client.core.sessions.create()

    # run workflow
    result = await session.run("test_env_workflow")

    assert result == "var_1: z, var_2: y, api_key: 123"
