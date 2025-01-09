import asyncio
import multiprocessing
import subprocess
import time
from pathlib import Path

import pytest
import pytest_asyncio

from llama_deploy import (
    ControlPlaneConfig,
    WorkflowServiceConfig,
    deploy_core,
    deploy_workflow,
)
from llama_deploy.message_queues import RedisMessageQueue, RedisMessageQueueConfig

from .workflow import BasicWorkflow


@pytest.fixture(scope="session")
def redis_service():
    compose_file = Path(__file__).resolve().parent / "docker-compose.yml"
    proc = subprocess.Popen(
        ["docker", "compose", "-f", f"{compose_file}", "up", "-d", "--wait"]
    )
    proc.communicate()
    yield
    subprocess.Popen(["docker", "compose", "-f", f"{compose_file}", "down"])
    proc.communicate()


@pytest_asyncio.fixture()
async def mq(redis_service):
    mq = RedisMessageQueue()
    yield mq
    await mq.cleanup()


def run_workflow_one():
    asyncio.run(
        deploy_workflow(
            BasicWorkflow(timeout=10, name="Workflow one"),
            WorkflowServiceConfig(
                host="127.0.0.1",
                port=8003,
                service_name="basic",
            ),
            ControlPlaneConfig(topic_namespace="core_one", port=8001),
        )
    )


def run_workflow_two():
    asyncio.run(
        deploy_workflow(
            BasicWorkflow(timeout=10, name="Workflow two"),
            WorkflowServiceConfig(
                host="127.0.0.1",
                port=8004,
                service_name="basic",
            ),
            ControlPlaneConfig(topic_namespace="core_two", port=8002),
        )
    )


def run_core_one():
    asyncio.run(
        deploy_core(
            ControlPlaneConfig(topic_namespace="core_one", port=8001),
            RedisMessageQueueConfig(),
        )
    )


def run_core_two():
    asyncio.run(
        deploy_core(
            ControlPlaneConfig(topic_namespace="core_two", port=8002),
            RedisMessageQueueConfig(),
        )
    )


@pytest.fixture
def control_planes(redis_service):
    p1 = multiprocessing.Process(target=run_core_one)
    p1.start()

    p2 = multiprocessing.Process(target=run_core_two)
    p2.start()

    time.sleep(3)

    p3 = multiprocessing.Process(target=run_workflow_one)
    p3.start()

    p4 = multiprocessing.Process(target=run_workflow_two)
    p4.start()

    time.sleep(3)

    yield

    p1.terminate()
    p2.terminate()
    p3.terminate()
    p4.terminate()
