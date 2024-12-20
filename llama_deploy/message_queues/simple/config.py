from logging import getLogger
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = getLogger(__name__)


class SimpleMessageQueueConfig(BaseSettings):
    """Simple message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="SIMPLE_MESSAGE_QUEUE_")

    type: Literal["simple"] = Field(default="simple", exclude=True)
    host: str = "127.0.0.1"
    port: int = 8001
    client_kwargs: dict[str, Any] = Field(default_factory=dict)
    raise_exceptions: bool = False
    use_ssl: bool = False

    @property
    def base_url(self) -> str:
        protocol = "https" if self.use_ssl else "http"
        if self.port != 80:
            return f"{protocol}://{self.host}:{self.port}/"
        return f"{protocol}://{self.host}/"
