from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLAMA_DEPLOY_")

    api_server_url: str = "http://localhost:4501"
    disable_ssl: bool = False
    timeout: float = 120.0
    poll_interval: float = 0.5
