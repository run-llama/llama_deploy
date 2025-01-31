import multiprocessing
import time
from pathlib import Path

import httpx
import pytest
import uvicorn

from llama_deploy.client import Client


def run_apiserver():
    uvicorn.run("llama_deploy.apiserver:app", host="127.0.0.1", port=4501)


def wait_for_healthcheck():
    while True:
        retries = 1
        try:
            httpx.get("http://127.0.0.1:4501/status/")
            break
        except httpx.ConnectError:
            if retries > 5:
                raise
            time.sleep(retries)


@pytest.fixture(scope="function")
def apiserver():
    p = multiprocessing.Process(target=run_apiserver)
    p.start()
    wait_for_healthcheck()

    yield

    p.kill()
    p.join()
    p.close()


@pytest.fixture(scope="function")
def apiserver_with_rc(monkeypatch):
    here = Path(__file__).parent
    rc_path = here / "rc"
    monkeypatch.setenv("LLAMA_DEPLOY_APISERVER_RC_PATH", str(rc_path))

    p = multiprocessing.Process(target=run_apiserver)
    p.start()
    wait_for_healthcheck()

    yield

    p.kill()
    p.join()
    p.close()


@pytest.fixture
def client():
    return Client(api_server_url="http://localhost:4501")
