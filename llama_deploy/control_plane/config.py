from typing import List
from urllib.parse import urlparse

from llama_index.core.storage.kvstore.types import BaseKVStore
from pydantic_settings import BaseSettings, SettingsConfigDict


class ControlPlaneConfig(BaseSettings):
    """Control plane configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CONTROL_PLANE_", arbitrary_types_allowed=True
    )

    services_store_key: str = "services"
    tasks_store_key: str = "tasks"
    session_store_key: str = "sessions"
    step_interval: float = 0.1
    host: str = "127.0.0.1"
    port: int = 8000
    internal_host: str | None = None
    internal_port: int | None = None
    running: bool = True
    cors_origins: List[str] | None = None
    topic_namespace: str = "llama_deploy"
    state_store_uri: str | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


def parse_state_store_uri(uri: str) -> BaseKVStore:
    bits = urlparse(uri)

    if bits.scheme == "redis":
        try:
            from llama_index.storage.kvstore.redis import RedisKVStore  # type: ignore

            return RedisKVStore(uri=uri)
        except ImportError:
            msg = (
                f"key-value store {bits.scheme} is not available, please install the required "
                "llama_index integration with 'pip install llama-index-storage-kvstore-redis'."
            )
            raise ValueError(msg)
    elif bits.scheme == "mongodb+srv":
        try:
            from llama_index.storage.kvstore.mongodb import (  # type:ignore
                MongoDBKVStore,
            )

            return MongoDBKVStore(uri=uri)
        except ImportError:
            msg = (
                f"key-value store {bits.scheme} is not available, please install the required "
                "llama_index integration with 'pip install llama-index-storage-kvstore-mongodb'."
            )
            raise ValueError(msg)
    else:
        msg = f"key-value store '{bits.scheme}' is not supported."
        raise ValueError(msg)
