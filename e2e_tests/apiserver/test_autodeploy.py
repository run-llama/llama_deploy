import asyncio
from pathlib import Path

import pytest
import uvicorn

from llama_deploy.apiserver.app import app
from llama_deploy.apiserver.settings import ApiserverSettings


@pytest.mark.asyncio
async def test_autodeploy(client, monkeypatch):
    here = Path(__file__).parent
    rc_path = here / "rc"
    monkeypatch.setenv("LLAMA_DEPLOY_APISERVER_RC_PATH", str(rc_path))
    settings = ApiserverSettings()
    assert settings.rc_path == rc_path

    cfg = uvicorn.Config(app, host=settings.host, port=settings.port)
    server = uvicorn.Server(cfg)
    server_task = asyncio.create_task(server.serve())

    await asyncio.sleep(3)

    status = await client.apiserver.status()

    # tear down
    try:
        await server.shutdown()
        server_task.cancel()
    except asyncio.CancelledError:
        pass

    # assert
    assert "AutoDeployed" in status.deployments
