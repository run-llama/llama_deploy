import asyncio
import multiprocessing
import time

import pytest

from llama_deploy import (
    ControlPlaneConfig,
    SimpleMessageQueueConfig,
    WorkflowServiceConfig,
    deploy_core,
    deploy_workflow,
)

from .workflow import HumanInTheLoopWorkflow


def run_async_core():
    asyncio.run(deploy_core(ControlPlaneConfig(), SimpleMessageQueueConfig()))


@pytest.fixture(scope="package")
def core():
    p = multiprocessing.Process(target=run_async_core)
    p.start()
    time.sleep(5)

    yield

    p.kill()


def run_async_workflow():
    asyncio.run(
        deploy_workflow(
            HumanInTheLoopWorkflow(timeout=60),
            WorkflowServiceConfig(
                host="127.0.0.1",
                port=8002,
                service_name="hitl_workflow",
            ),
            ControlPlaneConfig(),
        )
    )


@pytest.fixture(scope="package")
def services(core):
    p = multiprocessing.Process(target=run_async_workflow)
    p.start()
    time.sleep(5)

    yield

    p.kill()
