from llama_deploy import (
    deploy_core,
    ControlPlaneConfig,
)
from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueueConfig


control_plane_config = ControlPlaneConfig(
    host="control_plane",
    port=8000,
    external_host="0.0.0.0",
    external_port=8000,
)
message_queue_config = RabbitMQMessageQueueConfig(
    username="guest", password="guest", host="rabbitmq", port=5672
)

if __name__ == "__main__":
    import asyncio

    asyncio.run(
        deploy_core(
            control_plane_config=control_plane_config,
            message_queue_config=message_queue_config,
        )
    )
