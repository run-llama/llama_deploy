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
    deployments_path: Path | None = Field(
        default=None,
        description="Path to the folder where deployments will create their root path, defaults to a temp dir",
    )
    deployment_file_path: str | None = Field(
        default=None,
        description="Optional path, relative to the rc_path, where the deployment file is located. If not provided, will glob all .yml/.yaml files in the rc_path",
    )
    use_tls: bool = Field(
        default=False,
        description="Use TLS (HTTPS) to communicate with the API Server",
    )

    # Metrics collection settings
    prometheus_enabled: bool = Field(
        default=True,
        description="Whether to enable the Prometheus metrics exporter along with the API Server",
    )
    prometheus_port: int = Field(
        default=9000,
        description="The port where to serve Prometheus metrics",
    )

    # Tracing settings
    tracing_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry tracing. Defaults to False.",
    )
    tracing_service_name: str = Field(
        default="llama-deploy-apiserver",
        description="Service name for tracing. Defaults to 'llama-deploy-apiserver'.",
    )
    tracing_exporter: str = Field(
        default="console",
        description="Trace exporter type: 'console', 'jaeger', 'otlp'. Defaults to 'console'.",
    )
    tracing_endpoint: str | None = Field(
        default=None,
        description="Trace exporter endpoint. Required for 'jaeger' and 'otlp' exporters.",
    )
    tracing_sample_rate: float = Field(
        default=1.0,
        description="Trace sampling rate (0.0 to 1.0). Defaults to 1.0 (100% sampling).",
    )
    tracing_insecure: bool = Field(
        default=True,
        description="Use insecure connection for OTLP exporter. Defaults to True.",
    )
    tracing_timeout: int = Field(
        default=30,
        description="Timeout in seconds for trace export. Defaults to 30.",
    )

    @property
    def url(self) -> str:
        protocol = "https://" if self.use_tls else "http://"
        if self.port == 80:
            return f"{protocol}{self.host}"
        return f"{protocol}{self.host}:{self.port}"


settings = ApiserverSettings()
