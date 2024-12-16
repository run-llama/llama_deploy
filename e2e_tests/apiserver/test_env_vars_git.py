import asyncio
from pathlib import Path

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_read_env_vars_git(apiserver, client):
    here = Path(__file__).parent

    with open(here / "deployments" / "deployment_env_git.yml") as f:
        await client.apiserver.deployments.create(f)
        await asyncio.sleep(5)

    session = await client.core.sessions.create()

    # run workflow
    result = await session.run(
        "workflow_git", env_vars_to_read=["VAR_1", "VAR_2", "API_KEY"]
    )

    assert result == "VAR_1: x, VAR_2: y, API_KEY: 123"
