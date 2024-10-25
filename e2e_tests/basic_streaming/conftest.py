import asyncio
import multiprocessing
import time

import pytest

from llama_deploy import (
    ControlPlaneConfig,
    WorkflowServiceConfig,
    deploy_workflow,
)

from .workflow import StreamingWorkflow


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


@pytest.fixture
def services(core):
    p = multiprocessing.Process(target=run_async_workflow)
    p.start()
    time.sleep(5)

    yield

    p.kill()
