import sys
import warnings
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Union

if sys.version_info >= (3, 11):
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self

import yaml
from pydantic import BaseModel, Field, model_validator

from llama_deploy.control_plane.server import ControlPlaneConfig
from llama_deploy.message_queues import (
    AWSMessageQueueConfig,
    KafkaMessageQueueConfig,
    RabbitMQMessageQueueConfig,
    RedisMessageQueueConfig,
    SimpleMessageQueueConfig,
    SolaceMessageQueueConfig,
)

MessageQueueConfig = Annotated[
    Union[
        AWSMessageQueueConfig,
        KafkaMessageQueueConfig,
        RabbitMQMessageQueueConfig,
        RedisMessageQueueConfig,
        SimpleMessageQueueConfig,
        SolaceMessageQueueConfig,
    ],
    Field(discriminator="type"),
]


class SourceType(str, Enum):
    """Supported types for the `Service.source` parameter."""

    git = "git"
    docker = "docker"
    local = "local"


class ServiceSource(BaseModel):
    """Configuration for the `source` parameter of a service."""

    type: SourceType
    location: str

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" in data and "location" not in data:
                warnings.warn(
                    "The 'name' field is deprecated. Use 'location' instead.",
                    DeprecationWarning,
                )
                data["location"] = data["name"]
        return data


class Service(BaseModel):
    """Configuration for a single service."""

    name: str
    source: ServiceSource
    import_path: str | None = Field(None, alias="import-path")
    host: str | None = None
    port: int | None = None
    env: dict[str, str] | None = Field(None)
    env_files: list[str] | None = Field(None, alias="env-files")
    python_dependencies: list[str] | None = Field(None, alias="python-dependencies")
    ts_dependencies: dict[str, str] | None = Field(None, alias="ts-dependencies")

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "path" in data and "import-path" not in data:
                warnings.warn(
                    "The 'path' field is deprecated. Use 'import-path' instead.",
                    DeprecationWarning,
                )
                data["import-path"] = data["path"]
        return data


class UIService(Service):
    pass


class DeploymentConfig(BaseModel):
    """Model definition mapping a deployment config file."""

    name: str
    control_plane: ControlPlaneConfig = Field(alias="control-plane")
    message_queue: MessageQueueConfig | None = Field(None, alias="message-queue")
    default_service: str | None = Field(None, alias="default-service")
    services: dict[str, Service]
    ui: UIService | None = None

    @classmethod
    def from_yaml_bytes(cls, src: bytes) -> Self:
        """Read config data from bytes containing yaml code."""
        config = yaml.safe_load(src) or {}
        return cls(**config)

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        """Read config data from a yaml file."""
        with open(path, "r") as yaml_file:
            config = yaml.safe_load(yaml_file) or {}

        return cls(**config)
