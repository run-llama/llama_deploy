from abc import ABC, abstractmethod
from enum import Enum, auto

from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig


class SyncPolicy(Enum):
    """Define the sync behaviour in case the destination target exists."""

    REPLACE = auto()
    MERGE = auto()
    SKIP = auto()
    FAIL = auto()


class SourceManager(ABC):
    """Protocol to be implemented by classes responsible for managing Deployment sources."""

    def __init__(self, config: DeploymentConfig) -> None:
        self._config = config

    @abstractmethod
    def sync(
        self,
        source: str,
        destination: str | None = None,
        sync_policy: SyncPolicy = SyncPolicy.REPLACE,
    ) -> None:  # pragma: no cover
        """Fetches resources from `source` so they can be used in a deployment.

        Optionally uses `destination` to store data when this makes sense for the
        specific source type.
        """
