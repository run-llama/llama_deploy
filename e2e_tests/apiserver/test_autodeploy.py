import multiprocessing
from pathlib import Path

import pytest

from llama_deploy.apiserver.settings import ApiserverSettings

from .conftest import run_apiserver, wait_for_healthcheck


@pytest.mark.asyncio
async def _test_autodeploy(client, monkeypatch):
    here = Path(__file__).parent
    rc_path = here / "rc"
    monkeypatch.setenv("LLAMA_DEPLOY_APISERVER_RC_PATH", str(rc_path))

    p = multiprocessing.Process(target=run_apiserver)
    p.start()
    wait_for_healthcheck()

    settings = ApiserverSettings()
    assert str(settings.rc_path).endswith("llama_deploy/e2e_tests/apiserver/rc")

    status = await client.apiserver.status()
    assert "AutoDeployed" in status.deployments

    p.terminate()
    p.join()
    p.close()
