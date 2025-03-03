from pathlib import Path
from typing import cast

import yaml
from pydantic import BaseModel, Field
from typing_extensions import Self

from .utils import DEFAULT_PROFILE_NAME, _default_config_path


class ConfigProfile(BaseModel):
    """Pydantic model representing a llamactl configuration profile."""

    server: str = "http://localhost:4501"
    insecure: bool = False
    timeout: float = 120.0


class Config(BaseModel):
    """Pydantic model representing a llamactl configuration."""

    current_profile: str
    profiles: dict[str, ConfigProfile]
    path: Path = Field(default_factory=_default_config_path)

    @classmethod
    def from_path(cls, config_file_path: Path) -> Self:
        """Get a Config instance from a configuration file."""
        with open(config_file_path) as f:
            config_dict = yaml.safe_load(f.read())

        config_dict["path"] = config_file_path
        return cls(**config_dict)

    def write(self) -> None:
        """Write the Config object in the configuration file."""
        with open(cast(Path, self.path), "w") as f:
            config_data = self.model_dump(exclude={"path"})
            yaml.safe_dump(config_data, f)


def load_config(path: Path | None = None) -> Config:
    if path is None:
        path = _default_config_path()
        if not path.exists():
            # Use default
            config = Config(
                current_profile=DEFAULT_PROFILE_NAME,
                profiles={DEFAULT_PROFILE_NAME: ConfigProfile()},
            )
            config.write()
            return config

    return Config.from_path(path)
