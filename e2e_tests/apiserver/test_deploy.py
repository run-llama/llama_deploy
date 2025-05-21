from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_deploy(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment1.yml"
    with open(deployment_fp) as f:
        await client.apiserver.deployments.create(f, base_path=deployment_fp.parent)

    status = await client.apiserver.status()
    assert "TestDeployment1" in status.deployments


def test_deploy_sync(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment1.yml"
    with open(deployment_fp) as f:
        client.sync.apiserver.deployments.create(f, base_path=deployment_fp.parent)

    assert "TestDeployment1" in client.sync.apiserver.status().deployments


@pytest.mark.asyncio
async def test_deploy_local(apiserver, client):
    here = Path(__file__).parent
    deployment_fp = here / "deployments" / "deployment2.yml"
    with open(deployment_fp) as f:
        await client.apiserver.deployments.create(
            f, base_path=str(deployment_fp.parent.resolve())
        )

    status = await client.apiserver.status()
    assert "TestDeployment2" in status.deployments
