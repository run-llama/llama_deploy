from typing import List

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

    @property
    def url(self) -> str:
        if self.port:
            return f"http://{self.host}:{self.port}"
        else:
            return f"http://{self.host}"
