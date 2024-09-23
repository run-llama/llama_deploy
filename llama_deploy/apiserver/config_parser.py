from enum import Enum
from pathlib import Path
from typing import Self, Annotated, Union, Literal

import yaml
from pydantic import BaseModel, Field

from llama_deploy.control_plane.server import ControlPlaneConfig
from llama_deploy.message_queues import (
    AWSMessageQueueConfig,
    KafkaMessageQueueConfig,
    RedisMessageQueueConfig,
    SimpleMessageQueueConfig,
    RabbitMQMessageQueueConfig,
)


class MessageQueueConfigAWS(BaseModel):
    queue_type: Literal["aws"] = Field("aws", alias="queue-type")
    config: AWSMessageQueueConfig


class MessageQueueConfigKafka(BaseModel):
    queue_type: Literal["kafka"] = Field("kafka", alias="queue-type")
    config: KafkaMessageQueueConfig


class MessageQueueConfigRabbitMQ(BaseModel):
    queue_type: Literal["rabbitmq"] = Field("rabbitmq", alias="queue-type")
    config: RabbitMQMessageQueueConfig


class MessageQueueConfigRedis(BaseModel):
    queue_type: Literal["redis"] = Field("redis", alias="queue-type")
    config: RedisMessageQueueConfig


class MessageQueueConfigSimple(BaseModel):
    queue_type: Literal["simple"] = Field("simple", alias="queue-type")
    config: SimpleMessageQueueConfig


MessageQueueConfig = Annotated[
    Union[
        MessageQueueConfigAWS,
        MessageQueueConfigKafka,
        MessageQueueConfigRabbitMQ,
        MessageQueueConfigRedis,
        MessageQueueConfigSimple,
    ],
    Field(discriminator="queue_type"),
]


class SourceType(str, Enum):
    """Supported types for the `Service.source` parameter."""

    git = "git"
    docker = "docker"


class ServiceSource(BaseModel):
    """Configuration for the `source` parameter of a service."""

    type: SourceType
    name: str


class Service(BaseModel):
    """Configuration for a single service."""

    name: str
    source: ServiceSource | None = None
    path: str | None = None
    port: int | None = None
    python_dependencies: list[str] | None = Field(None, alias="python-dependencies")
    ts_dependencies: dict[str, str] | None = Field(None, alias="ts-dependencies")


class Config(BaseModel):
    """Model definition mapping a deployment config file."""

    name: str
    control_plane: ControlPlaneConfig = Field(alias="control-plane")
    message_queue: MessageQueueConfig | None = Field(None, alias="message-queue")
    services: dict[str, Service]

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        """Read config data from a yaml file."""
        with open(path, "r") as yaml_file:
            config = yaml.safe_load(yaml_file) or {}
        return cls(**config)
