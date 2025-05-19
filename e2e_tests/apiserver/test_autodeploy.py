import pytest


@pytest.mark.asyncio
async def test_autodeploy(client, apiserver_with_rc):
    status = await client.apiserver.status()
    assert "AutoDeployed" in status.deployments
