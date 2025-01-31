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

    @property
    def url(self) -> str:
        if self.use_tls:
            return f"https://{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"
