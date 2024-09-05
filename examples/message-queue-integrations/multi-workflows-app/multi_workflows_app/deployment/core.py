import argparse
from llama_deploy import (
    deploy_core,
    ControlPlaneConfig,
)
from llama_deploy.message_queues.apache_kafka import KafkaMessageQueueConfig
from llama_deploy.message_queues.simple import SimpleMessageQueueConfig
from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueueConfig


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
    args = parser.parse_args()

    message_queue_config = message_queue_configs[args.message_queue]
    asyncio.run(
        deploy_core(
            control_plane_config=control_plane_config,
            message_queue_config=message_queue_config,
        )
    )
