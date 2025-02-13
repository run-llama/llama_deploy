from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiserverSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLAMA_DEPLOY_APISERVER_")

    host: str = Field(
        default="127.0.0.1",
        description="The host where to run the API Server",
    )
    port: int = Field(
        default=4501,
        description="The TCP port where to bind the API Server",
    )
    rc_path: Path = Field(
        default=Path("./.llama_deploy_rc"),
        description="Path to the folder containing the deployment configs that will be loaded at startup",
    )
    deployments_path: Path = Field(
        default=Path("./deployments"),
        description="Path to the folder where deployments will create their root path",
    )
    use_tls: bool = Field(
        default=False,
        description="Use TLS (HTTPS) to communicate with the API Server",
    )
    prometheus_enabled: bool = Field(
        default=True,
        description="Whether to enable the Prometheus metrics exporter along with the API Server",
    )
    prometheus_port: int = Field(
        default=9000,
        description="The port where to serve Prometheus metrics",
    )

    @property
    def url(self) -> str:
        protocol = "https://" if self.use_tls else "http://"
        if self.port == 80:
            return f"{protocol}{self.host}"
        return f"{protocol}{self.host}:{self.port}"
