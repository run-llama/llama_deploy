import asyncio
import multiprocessing
import subprocess
import time
from pathlib import Path

import pytest

from llama_deploy import ControlPlaneConfig, WorkflowServiceConfig
from llama_deploy.deploy import deploy_core, deploy_workflow
from llama_deploy.message_queues import RabbitMQMessageQueue, RabbitMQMessageQueueConfig

from .workflow import BasicWorkflow


@pytest.fixture(scope="package")
def rabbitmq_service():
    compose_file = Path(__file__).resolve().parent / "docker-compose.yml"
    proc = subprocess.Popen(
        ["docker", "compose", "-f", f"{compose_file}", "up", "-d", "--wait"]
    )
    proc.communicate()
    yield
    subprocess.Popen(["docker", "compose", "-f", f"{compose_file}", "down"])


@pytest.fixture
def mq(rabbitmq_service):
    return RabbitMQMessageQueue(RabbitMQMessageQueueConfig())


def run_workflow():
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


def run_core():
    asyncio.run(
        deploy_core(
            ControlPlaneConfig(topic_namespace="core_one", port=8001),
            RabbitMQMessageQueueConfig(),
        )
    )


@pytest.fixture
def control_plane(rabbitmq_service):
    p1 = multiprocessing.Process(target=run_core)
    p1.start()

    time.sleep(3)

    p2 = multiprocessing.Process(target=run_workflow)
    p2.start()

    yield

    p1.kill()
    p2.kill()
