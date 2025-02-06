from abc import ABC, abstractmethod

from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig


class SourceManager(ABC):
    """Protocol to be implemented by classes responsible for managing Deployment sources."""

    def __init__(self, config: DeploymentConfig) -> None:
        self._config = config

    @abstractmethod
    def sync(
        self, source: str, destination: str | None = None
    ) -> None:  # pragma: no cover
        """Fetches resources from `source` so they can be used in a deployment.

        Optionally uses `destination` to store data when this makes sense for the
        specific source type.
        """
