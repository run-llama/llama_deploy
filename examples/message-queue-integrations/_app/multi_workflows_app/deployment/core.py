import argparse
from llama_deploy import (
    deploy_core,
    ControlPlaneConfig,
)
from llama_deploy.message_queues.apache_kafka import KafkaMessageQueueConfig
from llama_deploy.message_queues.simple import SimpleMessageQueueConfig
from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueueConfig
from llama_deploy.message_queues.redis import RedisMessageQueueConfig
from llama_deploy.message_queues.aws import AWSMessageQueueConfig
from llama_deploy.message_queues.solace import SolaceMessageQueueConfig


control_plane_config = ControlPlaneConfig()

message_queue_configs = {
    "kafka": KafkaMessageQueueConfig,
    "rabbitmq": RabbitMQMessageQueueConfig,
    "redis": RedisMessageQueueConfig,
    "aws": AWSMessageQueueConfig,
    "simple": SimpleMessageQueueConfig,
    "solace": SolaceMessageQueueConfig,
}


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Deploy core services.")
    parser.add_argument(
        "-q",
        "--message-queue",
        choices=["rabbitmq", "simple", "kafka", "redis", "aws", "solace"],
        default="simple",
        type=str,
        help="The message queue to use.",
    )
    parser.add_argument(
        "--disable-message-queue",
        action="store_true",
        help="Whether to use the cached results or not.",
    )
    parser.add_argument(
        "--disable-control-plane",
        action="store_true",
        help="Whether to use the cached results or not.",
    )
    args = parser.parse_args()

    # initialize the message queue config
    message_queue_config = message_queue_configs[args.message_queue]()

    asyncio.run(
        deploy_core(
            control_plane_config=control_plane_config,
            message_queue_config=message_queue_config,
            disable_message_queue=args.disable_message_queue,
            disable_control_plane=args.disable_control_plane,
        )
    )
