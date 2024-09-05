import argparse
from llama_deploy import (
    deploy_core,
    ControlPlaneConfig,
)
from llama_deploy.message_queues.apache_kafka import KafkaMessageQueueConfig
from llama_deploy.message_queues.simple import SimpleMessageQueueConfig
from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueueConfig
from llama_deploy.message_queues.redis import RedisMessageQueueConfig


control_plane_config = ControlPlaneConfig(
    host="control_plane",
    port=8000,
    internal_host="0.0.0.0",
    internal_port=8000,
)

message_queue_configs = {
    "kafka": KafkaMessageQueueConfig(host="kafka", port=19092),
    "rabbitmq": RabbitMQMessageQueueConfig(
        username="guest", password="guest", host="rabbitmq", port=5672
    ),
    "redis": RedisMessageQueueConfig(host="redis", port=6379),
    "simple": SimpleMessageQueueConfig(
        host="message_queue", port=8002, internal_host="0.0.0.0", internal_port=8002
    ),
}


if __name__ == "__main__":
    import asyncio

    parser = argparse.ArgumentParser(description="Deploy core services.")
    parser.add_argument(
        "-q",
        "--message-queue",
        choices=["rabbitmq", "simple", "kafka", "redis"],
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

    message_queue_config = message_queue_configs[args.message_queue]
    asyncio.run(
        deploy_core(
            control_plane_config=control_plane_config,
            message_queue_config=message_queue_config,
            disable_message_queue=args.disable_message_queue,
            disable_control_plane=args.disable_control_plane,
        )
    )
