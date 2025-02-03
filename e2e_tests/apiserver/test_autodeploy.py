import pytest

from llama_deploy.apiserver.settings import ApiserverSettings


@pytest.mark.asyncio
async def test_autodeploy(client, apiserver_with_rc):
    settings = ApiserverSettings()
    assert str(settings.rc_path).endswith("llama_deploy/e2e_tests/apiserver/rc")

    status = await client.apiserver.status()
    assert "AutoDeployed" in status.deployments
