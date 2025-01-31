import multiprocessing
from pathlib import Path

import httpx
import pytest
import uvicorn
from tenacity import retry, stop_after_attempt, wait_exponential

from llama_deploy.client import Client


def run_apiserver():
    uvicorn.run("llama_deploy.apiserver:app", host="127.0.0.1", port=4501)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=10))
def wait_for_healthcheck():
    httpx.get("http://127.0.0.1:4501/status/")


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
