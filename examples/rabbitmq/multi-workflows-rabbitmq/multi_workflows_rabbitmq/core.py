from llama_deploy import (
    ControlPlaneConfig,
)
from llama_deploy.message_queues.rabbitmq import RabbitMQMessageQueueConfig


control_plane_config = ControlPlaneConfig()
message_queue_config = RabbitMQMessageQueueConfig()
