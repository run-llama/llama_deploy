import subprocess
from pathlib import Path

import pytest

from llama_deploy.message_queues import RabbitMQMessageQueue, RabbitMQMessageQueueConfig


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
