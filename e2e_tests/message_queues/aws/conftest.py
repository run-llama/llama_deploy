import asyncio
import multiprocessing
import os
import time

import pytest

from llama_deploy import (
    ControlPlaneConfig,
    WorkflowServiceConfig,
    deploy_core,
    deploy_workflow,
)
from llama_deploy.message_queues import AWSMessageQueue, AWSMessageQueueConfig

from .workflow import BasicWorkflow


@pytest.fixture
def mq():
    return AWSMessageQueue()


@pytest.fixture
def topic_prefix() -> str:
    """Use different SQS queues to allow tests to run in parallel"""
    return os.environ.get("TOPIC_PREFIX", "").replace(".", "_")


def run_workflow_one(topic_prefix):
    asyncio.run(
        deploy_workflow(
            BasicWorkflow(timeout=10, name="Workflow one"),
            WorkflowServiceConfig(
                host="127.0.0.1",
                port=8003,
                service_name="basic",
            ),
            ControlPlaneConfig(topic_namespace=f"{topic_prefix}core_one", port=8001),
        )
    )


def run_workflow_two(topic_prefix):
    asyncio.run(
        deploy_workflow(
            BasicWorkflow(timeout=10, name="Workflow two"),
            WorkflowServiceConfig(
                host="127.0.0.1",
                port=8004,
                service_name="basic",
            ),
            ControlPlaneConfig(topic_namespace=f"{topic_prefix}core_two", port=8002),
        )
    )


def run_core_one(topic_prefix):
    asyncio.run(
        deploy_core(
            ControlPlaneConfig(topic_namespace=f"{topic_prefix}core_one", port=8001),
            AWSMessageQueueConfig(),
        )
    )


def run_core_two(topic_prefix):
    asyncio.run(
        deploy_core(
            ControlPlaneConfig(topic_namespace=f"{topic_prefix}core_two", port=8002),
            AWSMessageQueueConfig(),
        )
    )


@pytest.fixture
def control_planes(kafka_service):
    p1 = multiprocessing.Process(target=run_core_one)
    p1.start()

    p2 = multiprocessing.Process(target=run_core_two)
    p2.start()

    time.sleep(3)

    p3 = multiprocessing.Process(target=run_workflow_one)
    p3.start()

    p4 = multiprocessing.Process(target=run_workflow_two)
    p4.start()

    yield

    p1.terminate()
    p2.terminate()
    p3.terminate()
    p4.terminate()
