from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_deploy(apiserver, client):
    here = Path(__file__).parent
    with open(here / "deployments" / "deployment1.yml") as f:
        await client.apiserver.deployments.create(f)

    status = await client.apiserver.status()
    assert "TestDeployment1" in status.deployments


def test_deploy_sync(apiserver, client):
    here = Path(__file__).parent
    with open(here / "deployments" / "deployment2.yml") as f:
        client.sync.apiserver.deployments.create(f)

    assert "TestDeployment2" in client.sync.apiserver.status().deployments
