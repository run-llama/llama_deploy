import asyncio
import os

from llama_deploy import deploy_core
from llama_deploy.message_queues.simple import SimpleMessageQueueConfig
from llama_deploy.message_queues.apache_kafka import KafkaMessageQueueConfig
from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueueConfig
from llama_deploy.message_queues.redis import RedisMessageQueueConfig
from llama_deploy.message_queues.aws import AWSMessageQueueConfig


CONFIGS = {
    "awssqs": AWSMessageQueueConfig(),
    "kafka": KafkaMessageQueueConfig(),
    "rabbitmq": RabbitMQMessageQueueConfig(),
    "redis": RedisMessageQueueConfig(),
    "simple": SimpleMessageQueueConfig(),
}


def strtobool(val: str) -> bool:
    """
    Convert a string representation of truth to True or False.

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True

    if val in ("n", "no", "f", "false", "off", "0"):
        return False

    msg = f"invalid truth value {val}"
    raise ValueError(msg)


DISABLE_CONTROL_PLANE = not strtobool(os.environ.get("RUN_CONTROL_PLANE", "true"))
DISABLE_MESSAGE_QUEUE = not strtobool(os.environ.get("RUN_MESSAGE_QUEUE", "true"))


async def run_deploy() -> None:
    await deploy_core(
        message_queue_config=CONFIGS[os.environ.get("MESSAGE_QUEUE_CONFIG", "simple")],
        disable_control_plane=DISABLE_CONTROL_PLANE,
        disable_message_queue=DISABLE_MESSAGE_QUEUE,
    )


if __name__ == "__main__":
    asyncio.run(run_deploy())
