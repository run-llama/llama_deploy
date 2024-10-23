from pydantic_settings import BaseSettings, SettingsConfigDict


class ClientSettings(BaseSettings):
    """The global settings for a Client instance.

    Settings can be manually defined before creating a Client instance, or defined with environment variables having
    names prefixed with the string `LLAMA_DEPLOY_`, e.g. `LLAMA_DEPLOY_DISABLE_SSL`.
    """

    model_config = SettingsConfigDict(env_prefix="LLAMA_DEPLOY_")

    api_server_url: str = "http://localhost:4501"
    disable_ssl: bool = False
    timeout: float = 120.0
    poll_interval: float = 0.5
