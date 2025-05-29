import asyncio
import multiprocessing
import time

import pytest

from llama_deploy import ControlPlaneConfig, SimpleMessageQueueConfig

from .utils import deploy_core


def run_async_core():
    asyncio.run(deploy_core(ControlPlaneConfig(), SimpleMessageQueueConfig()))


@pytest.fixture
def core():
    p = multiprocessing.Process(target=run_async_core)
    p.start()
    time.sleep(3)

    yield

    p.kill()
