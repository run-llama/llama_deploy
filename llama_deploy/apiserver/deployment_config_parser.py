import sys
import warnings
from enum import Enum
from pathlib import Path
from typing import Any, Optional

if sys.version_info >= (3, 11):
    from typing import Self
else:  # pragma: no cover
    from typing_extensions import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceType(str, Enum):
    """Supported types for the `Service.source` parameter."""

    git = "git"
    docker = "docker"
    local = "local"


class SyncPolicy(Enum):
    """Define the sync behaviour in case the destination target exists."""

    REPLACE = "replace"
    MERGE = "merge"
    SKIP = "skip"
    FAIL = "fail"


class ServiceSource(BaseModel):
    """Configuration for the `source` parameter of a service."""

    type: SourceType
    location: str
    sync_policy: Optional[SyncPolicy] = None

    @model_validator(mode="before")
    @classmethod
    def handle_deprecated_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" in data and "location" not in data:  # pragma: no cover
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
    import_path: str | None = Field(None)
    host: str | None = None
    port: int | None = None
    env: dict[str, str] | None = Field(None)
    env_files: list[str] | None = Field(None)
    python_dependencies: list[str] | None = Field(None)
    ts_dependencies: dict[str, str] | None = Field(None)

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "path" in data and "import-path" not in data:  # pragma: no cover
                warnings.warn(
                    "The 'path' field is deprecated. Use 'import-path' instead.",
                    DeprecationWarning,
                )
                data["import-path"] = data["path"]

            # Handle YAML aliases
            if "import-path" in data:
                data["import_path"] = data.pop("import-path")
            if "env-files" in data:
                data["env_files"] = data.pop("env-files")
            if "python-dependencies" in data:
                data["python_dependencies"] = data.pop("python-dependencies")
            if "ts-dependencies" in data:
                data["ts_dependencies"] = data.pop("ts-dependencies")

        return data


class UIService(Service):
    port: int | None = Field(
        default=3000,
        description="The TCP port to use for the nextjs server",
    )


class DeploymentConfig(BaseModel):
    """Model definition mapping a deployment config file."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    name: str
    default_service: str | None = Field(None)
    services: dict[str, Service]
    ui: UIService | None = None

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, data: Any) -> Any:
        # Handle YAML aliases
        if isinstance(data, dict):
            if "control-plane" in data:
                data["control_plane"] = data.pop("control-plane")
            if "message-queue" in data:
                data["message_queue"] = data.pop("message-queue")
            if "default-service" in data:
                data["default_service"] = data.pop("default-service")

        return data

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
