from abc import ABC, abstractmethod
from pathlib import Path

from llama_deploy.apiserver.deployment_config_parser import DeploymentConfig, SyncPolicy


class SourceManager(ABC):
    """Protocol to be implemented by classes responsible for managing Deployment sources."""

    def __init__(self, config: DeploymentConfig, base_path: Path | None = None) -> None:
        self._config = config
        self._base_path = base_path

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

    def relative_path(self, source: str) -> str:
        """Unfortunately, there's a difference in behavior of how the source managers sync.
        The local source manager syncs the source into the <destination_path>/<source>, whereas
        the git source manager just syncs the source into the <destination_path>. This is a temporary shim, since
        changing this behavior is a breaking change to deployment.yaml configurations. Local source manager
        overrides it. In a future major version, this behavior will be made consistent"""
        return ""
