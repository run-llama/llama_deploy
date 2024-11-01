import asyncio
import multiprocessing
import time

import pytest

from llama_deploy import (
    ControlPlaneConfig,
    WorkflowServiceConfig,
    deploy_workflow,
)

from .workflow import HumanInTheLoopWorkflow


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


@pytest.fixture
def services(core):
    p = multiprocessing.Process(target=run_async_workflow)
    p.start()
    time.sleep(5)

    yield

    p.kill()