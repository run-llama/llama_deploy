import asyncio
import os

from llama_deploy import deploy_core
from llama_deploy.message_queues.simple import SimpleMessageQueueConfig
from llama_deploy.message_queues.apache_kafka import KafkaMessageQueueConfig
from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueueConfig
from llama_deploy.message_queues.redis import RedisMessageQueueConfig


CONFIGS = {
    "kafka": KafkaMessageQueueConfig(),
    "rabbitmq": RabbitMQMessageQueueConfig(),
    "redis": RedisMessageQueueConfig(),
    "simple": SimpleMessageQueueConfig(),
}


async def run_deploy() -> None:
    await deploy_core(
        message_queue_config=CONFIGS[os.environ.get("MESSAGE_QUEUE_CONFIG", "simple")],
        disable_control_plane=True,
    )


if __name__ == "__main__":
    asyncio.run(run_deploy())
