import multiprocessing
import time

import pytest
import uvicorn

from llama_deploy.client import Client


def run_async_apiserver():
    uvicorn.run("llama_deploy.apiserver:app", host="127.0.0.1", port=4501)


@pytest.fixture(scope="module")
def apiserver():
    p = multiprocessing.Process(target=run_async_apiserver)
    p.start()
    time.sleep(3)

    yield

    p.kill()


@pytest.fixture
def client():
    return Client(api_server_url="http://localhost:4501")
