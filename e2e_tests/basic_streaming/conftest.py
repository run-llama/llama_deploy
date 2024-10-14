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

from .workflow import StreamingWorkflow


def run_async_core():
    asyncio.run(deploy_core(ControlPlaneConfig(), SimpleMessageQueueConfig()))


def run_async_workflow():
    asyncio.run(
        deploy_workflow(
            StreamingWorkflow(timeout=10),
            WorkflowServiceConfig(
                host="127.0.0.1",
                port=8002,
                service_name="streaming_workflow",
            ),
            ControlPlaneConfig(),
        )
    )


@pytest.fixture(scope="package")
def services():
    p1 = multiprocessing.Process(target=run_async_core)
    p1.start()
    time.sleep(5)

    p2 = multiprocessing.Process(target=run_async_workflow)
    p2.start()
    time.sleep(3)

    yield

    p1.kill()
    p2.kill()
