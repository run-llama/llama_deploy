from logging import getLogger
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = getLogger(__name__)


class SimpleMessageQueueConfig(BaseSettings):
    """Simple message queue configuration."""

    model_config = SettingsConfigDict(env_prefix="SIMPLE_MESSAGE_QUEUE_")

    type: Literal["simple"] = Field(default="simple", exclude=True)
    host: str = "127.0.0.1"
    port: int | None = 8001
