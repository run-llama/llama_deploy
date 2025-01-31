import multiprocessing

import httpx
import pytest
import uvicorn
from tenacity import retry, stop_after_attempt, wait_exponential

from llama_deploy.client import Client


def run_apiserver():
    uvicorn.run("llama_deploy.apiserver:app", host="127.0.0.1", port=4501)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=1, max=10))
def wait_for_healthcheck():
    response = httpx.get("http://127.0.0.1:4501/status/")
    response.raise_for_status()


@pytest.fixture(scope="function")
def apiserver():
    p = multiprocessing.Process(target=run_apiserver)
    p.start()
    wait_for_healthcheck()

    yield

    p.terminate()
    p.join()
    p.close()


@pytest.fixture
def client():
    return Client(api_server_url="http://localhost:4501")
